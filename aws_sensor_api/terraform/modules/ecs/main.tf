variable "env" {}
variable "aws_region" {}
variable "vpc_id" {}
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "ecr_image_tag" {}
variable "database_url" { sensitive = true }
variable "s3_bucket" {}
variable "ecs_desired_count" { type = number }

resource "aws_ecr_repository" "api" {
  name                 = "oem-sensor-api-${var.env}"
  image_tag_mutability = "MUTABLE"
  lifecycle {
    ignore_changes = [image_scanning_configuration]
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{ rulePriority = 1; description = "Keep last 10"; action = { type = "expire" }
               selection = { tagStatus = "any"; countType = "imageCountMoreThan"; countNumber = 10 } }]
  })
}

resource "aws_ecs_cluster" "main" {
  name = "oem-sensor-${var.env}"
  setting { name = "containerInsights"; value = "enabled" }
}

resource "aws_iam_role" "task_execution" {
  name               = "oem-sensor-task-exec-${var.env}"
  assume_role_policy = jsonencode({ Version = "2012-10-17"; Statement = [{ Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" }; Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "oem-sensor-task-${var.env}"
  assume_role_policy = jsonencode({ Version = "2012-10-17"; Statement = [{ Effect = "Allow"; Principal = { Service = "ecs-tasks.amazonaws.com" }; Action = "sts:AssumeRole" }] })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/oem-sensor-api/${var.env}"
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "api" {
  family                   = "oem-sensor-api-${var.env}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions    = jsonencode([{
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.ecr_image_tag}"
    essential = true
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "DATABASE_URL"; value = var.database_url },
      { name = "S3_BUCKET";    value = var.s3_bucket },
      { name = "AWS_REGION";   value = var.aws_region },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = { "awslogs-group" = aws_cloudwatch_log_group.api.name; "awslogs-region" = var.aws_region; "awslogs-stream-prefix" = "api" }
    }
  }])
}

resource "aws_security_group" "alb" {
  name   = "oem-sensor-alb-${var.env}"
  vpc_id = var.vpc_id
  ingress { from_port = 80; to_port = 80; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0;  to_port = 0;  protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "ecs" {
  name   = "oem-sensor-ecs-${var.env}"
  vpc_id = var.vpc_id
  ingress { from_port = 8000; to_port = 8000; protocol = "tcp"; security_groups = [aws_security_group.alb.id] }
  egress  { from_port = 0;    to_port = 0;    protocol = "-1"; cidr_blocks     = ["0.0.0.0/0"] }
}

resource "aws_lb" "main" {
  name               = "oem-sensor-alb-${var.env}"
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "api" {
  name        = "oem-sensor-tg-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check { path = "/health"; healthy_threshold = 2; interval = 30 }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action    { type = "forward"; target_group_arn = aws_lb_target_group.api.arn }
}

resource "aws_ecs_service" "api" {
  name            = "oem-sensor-api-${var.env}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  launch_type     = "FARGATE"
  desired_count   = var.ecs_desired_count
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
}

output "alb_dns_name" { value = aws_lb.main.dns_name }
output "ecr_repo_url" { value = aws_ecr_repository.api.repository_url }
output "ecs_sg_id"    { value = aws_security_group.ecs.id }
output "task_role_arn"{ value = aws_iam_role.task.arn }
