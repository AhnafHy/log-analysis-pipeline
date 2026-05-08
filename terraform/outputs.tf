output "logs_bucket" {
  value       = aws_s3_bucket.logs.id
  description = "S3 bucket storing log data"
}

output "athena_results_bucket" {
  value       = aws_s3_bucket.athena_results.id
  description = "S3 bucket for Athena query results"
}

output "firehose_stream_name" {
  value       = aws_kinesis_firehose_delivery_stream.logs.name
  description = "Kinesis Firehose delivery stream name"
}

output "glue_database" {
  value       = aws_glue_catalog_database.logs.name
  description = "Glue catalog database for Athena"
}

output "athena_workgroup" {
  value       = aws_athena_workgroup.main.name
  description = "Athena workgroup name"
}

output "lambda_function_name" {
  value       = aws_lambda_function.log_generator.function_name
  description = "Log generator Lambda function name"
}