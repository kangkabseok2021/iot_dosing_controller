output "alb_dns_name"   { value = module.ecs.alb_dns_name }
output "rds_endpoint"   { value = module.rds.endpoint; sensitive = true }
output "s3_bucket_name" { value = module.s3_iam.bucket_name }
output "ecr_repo_url"   { value = module.ecs.ecr_repo_url }
