resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${random_string.bucket_suffix.result}"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-data"
  })
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "cleanup-old-artifacts"
    status = "Enabled"

    filter {
      prefix = "mlflow-artifacts/"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    filter {
      prefix = "raw-data/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

output "s3_bucket_name" {
  description = "S3 bucket name for data and artifacts"
  value       = aws_s3_bucket.data.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.data.arn
}
