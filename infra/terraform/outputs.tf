output "app_url" {
  description = "對外網址"
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "tdx_secret_name" {
  description = "到 Secrets Manager Console 填入 TDX_CLIENT_ID / TDX_CLIENT_SECRET"
  value       = aws_secretsmanager_secret.tdx.name
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "alb_dns_name" {
  description = "直接連會回 403（只接受 CloudFront），用來驗證 ALB 有擋住"
  value       = aws_lb.app.dns_name
}

# ----- 以下填到 GitHub repo 的 Settings → Secrets and variables → Actions → Variables -----

output "github_variables" {
  value = {
    AWS_REGION                 = var.aws_region
    AWS_DEPLOY_ROLE_ARN        = aws_iam_role.github_deploy.arn
    ECR_REPOSITORY             = aws_ecr_repository.app.name
    ECS_CLUSTER                = aws_ecs_cluster.main.name
    ECS_SERVICE                = aws_ecs_service.app.name
    ECS_TASK_FAMILY            = aws_ecs_task_definition.app.family
    CLOUDFRONT_DISTRIBUTION_ID = aws_cloudfront_distribution.app.id
    APP_URL                    = "https://${aws_cloudfront_distribution.app.domain_name}"
  }
}
