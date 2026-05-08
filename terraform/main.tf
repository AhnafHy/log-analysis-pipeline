provider "aws" {
  region = var.aws_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

# ─── S3 BUCKET FOR LOGS ─────────────────────────────────────
resource "aws_s3_bucket" "logs" {
  bucket        = "${var.project_name}-logs-${random_id.suffix.hex}"
  force_destroy = true
  tags = { Name = "${var.project_name}-logs" }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    filter { prefix = "logs/" }
    expiration { days = var.log_retention_days }
  }
}

# ─── S3 BUCKET FOR ATHENA RESULTS ───────────────────────────
resource "aws_s3_bucket" "athena_results" {
  bucket        = "${var.project_name}-athena-${random_id.suffix.hex}"
  force_destroy = true
  tags = { Name = "${var.project_name}-athena-results" }
}

# ─── IAM ROLE FOR FIREHOSE ──────────────────────────────────
resource "aws_iam_role" "firehose_role" {
  name = "${var.project_name}-firehose-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "firehose_s3_policy" {
  name = "firehose-s3-access"
  role = aws_iam_role.firehose_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:AbortMultipartUpload",
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads",
        "s3:PutObject"
      ]
      Resource = [
        aws_s3_bucket.logs.arn,
        "${aws_s3_bucket.logs.arn}/*"
      ]
    }]
  })
}

# ─── KINESIS FIREHOSE ───────────────────────────────────────
resource "aws_kinesis_firehose_delivery_stream" "logs" {
  name        = "${var.project_name}-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn           = aws_iam_role.firehose_role.arn
    bucket_arn         = aws_s3_bucket.logs.arn
    prefix             = "logs/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/"
    buffering_size     = var.firehose_buffer_size
    buffering_interval = var.firehose_buffer_interval
    compression_format = "GZIP"
  }

  tags = { Name = "${var.project_name}-stream" }
}

# ─── IAM ROLE FOR LAMBDA ────────────────────────────────────
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_firehose_policy" {
  name = "firehose-access"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
      Resource = aws_kinesis_firehose_delivery_stream.logs.arn
    }]
  })
}

# ─── LAMBDA FUNCTION ────────────────────────────────────────
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/log_generator.py"
  output_path = "${path.module}/../lambda/log_generator.zip"
}

resource "aws_lambda_function" "log_generator" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-generator"
  role             = aws_iam_role.lambda_role.arn
  handler          = "log_generator.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      FIREHOSE_STREAM_NAME = aws_kinesis_firehose_delivery_stream.logs.name
      BATCH_SIZE           = "100"
    }
  }

  tags = { Name = "${var.project_name}-generator" }
}

# ─── EVENTBRIDGE SCHEDULE ───────────────────────────────────
resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project_name}-schedule"
  description         = "Trigger log generator every minute"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "LogGeneratorLambda"
  arn       = aws_lambda_function.log_generator.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.log_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}

# ─── CLOUDWATCH ALARMS ──────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Lambda error rate too high"
  dimensions = {
    FunctionName = aws_lambda_function.log_generator.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "firehose_delivery" {
  alarm_name          = "${var.project_name}-delivery-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DeliveryToS3.DataFreshness"
  namespace           = "AWS/Firehose"
  period              = 300
  statistic           = "Maximum"
  threshold           = 900
  alarm_description   = "Firehose delivery delay exceeding 15 minutes"
  dimensions = {
    DeliveryStreamName = aws_kinesis_firehose_delivery_stream.logs.name
  }
}

# ─── GLUE DATABASE FOR ATHENA ───────────────────────────────
resource "aws_glue_catalog_database" "logs" {
  name = replace("${var.project_name}_db", "-", "_")
}

# ─── ATHENA WORKGROUP ───────────────────────────────────────
resource "aws_athena_workgroup" "main" {
  name = "${var.project_name}-workgroup"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/results/"
    }
  }

  tags = { Name = "${var.project_name}-workgroup" }
}