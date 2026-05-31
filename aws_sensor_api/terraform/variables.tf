variable "env"              { type = string; default = "dev" }
variable "aws_region"       { type = string; default = "eu-central-1" }
variable "db_instance_class"{ type = string; default = "db.t3.micro" }
variable "ecs_desired_count"{ type = number; default = 2 }
variable "ecr_image_tag"    { type = string; default = "latest" }
