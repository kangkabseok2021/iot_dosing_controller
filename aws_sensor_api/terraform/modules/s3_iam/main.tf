variable "env" {}
variable "aws_region" {}
variable "ecs_task_role_arn" {}

resource "aws_s3_bucket" "events" {
  bucket = "oem-sensor-events-${var.env}"
}

resource "aws_s3_bucket_versioning" "events" {
  bucket = aws_s3_bucket.events.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "events" {
  bucket = aws_s3_bucket.events.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket_public_access_block" "events" {
  bucket                  = aws_s3_bucket.events.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "events" {
  bucket = aws_s3_bucket.events.id
  rule {
    id     = "archive-to-glacier"
    status = "Enabled"
    filter { prefix = "events/" }
    transition { days = 90; storage_class = "GLACIER" }
  }
}

resource "aws_iam_role_policy" "s3_write" {
  name   = "oem-sensor-s3-write-${var.env}"
  role   = split("/", var.ecs_task_role_arn)[1]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["s3:PutObject", "s3:GetObject"]; Resource = "${aws_s3_bucket.events.arn}/events/*" },
      { Effect = "Allow"; Action = ["logs:CreateLogStream", "logs:PutLogEvents"]; Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/oem-sensor-api/*" }
    ]
  })
}

output "bucket_name" { value = aws_s3_bucket.events.bucket }
