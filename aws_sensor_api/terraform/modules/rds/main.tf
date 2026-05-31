variable "env" {}
variable "db_instance_class" {}
variable "private_subnet_ids" { type = list(string) }
variable "vpc_id" {}
variable "ecs_sg_id" {}

resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/oem-sensor/${var.env}/db_password"
  type  = "SecureString"
  value = random_password.db.result
}

resource "aws_db_subnet_group" "main" {
  name       = "oem-sensor-rds-${var.env}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name   = "oem-sensor-rds-${var.env}"
  vpc_id = var.vpc_id
  ingress { from_port = 5432; to_port = 5432; protocol = "tcp"; security_groups = [var.ecs_sg_id] }
}

resource "aws_db_instance" "main" {
  identifier             = "oem-sensor-${var.env}"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  storage_encrypted      = true
  username               = "apiuser"
  password               = random_password.db.result
  db_name                = "sensordb"
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  backup_retention_period = 7
  skip_final_snapshot    = true
  deletion_protection    = false
}

output "endpoint"     { value = aws_db_instance.main.endpoint; sensitive = true }
output "database_url" {
  value     = "postgresql+asyncpg://apiuser:${random_password.db.result}@${aws_db_instance.main.endpoint}/sensordb"
  sensitive = true
}
