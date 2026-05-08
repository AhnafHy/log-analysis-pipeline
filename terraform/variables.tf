variable "aws_region" {
  default = "us-east-2"
}

variable "project_name" {
  default = "log-analysis-pipeline"
}

variable "log_retention_days" {
  default = 7
}

variable "firehose_buffer_size" {
  description = "Buffer size in MB before Firehose delivers to S3"
  default     = 5
}

variable "firehose_buffer_interval" {
  description = "Buffer interval in seconds before Firehose delivers to S3"
  default     = 60
}