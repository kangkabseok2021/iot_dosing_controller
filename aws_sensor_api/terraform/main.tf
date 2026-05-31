terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
  backend "s3" {
    bucket         = "tf-state-oem-sensor-api"
    key            = "aws-sensor-api/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "tf-state-lock"
    encrypt        = true
  }
}

provider "aws" { region = var.aws_region }

module "vpc"     { source = "./modules/vpc";     aws_region = var.aws_region; env = var.env }
module "s3_iam"  { source = "./modules/s3_iam";  env = var.env; aws_region = var.aws_region; ecs_task_role_arn = module.ecs.task_role_arn }
module "rds"     { source = "./modules/rds";     env = var.env; db_instance_class = var.db_instance_class; private_subnet_ids = module.vpc.private_subnet_ids; vpc_id = module.vpc.vpc_id; ecs_sg_id = module.ecs.ecs_sg_id }
module "ecs"     { source = "./modules/ecs";     env = var.env; aws_region = var.aws_region; vpc_id = module.vpc.vpc_id; public_subnet_ids = module.vpc.public_subnet_ids; private_subnet_ids = module.vpc.private_subnet_ids; ecr_image_tag = var.ecr_image_tag; database_url = module.rds.database_url; s3_bucket = module.s3_iam.bucket_name; ecs_desired_count = var.ecs_desired_count }
