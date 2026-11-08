locals {
  container_name = "app"
  container_port = 8000

  tdx_secrets = [
    { name = "TDX_CLIENT_ID", valueFrom = "${aws_secretsmanager_secret.tdx.arn}:TDX_CLIENT_ID::" },
    { name = "TDX_CLIENT_SECRET", valueFrom = "${aws_secretsmanager_secret.tdx.arn}:TDX_CLIENT_SECRET::" },
  ]
}

resource "aws_ecs_cluster" "main" {
  name = var.project
  setting {
    name  = "containerInsights"
    value = "disabled" # 省成本；需要更細的指標時再開
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.project
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name         = local.container_name
    image        = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
    essential    = true
    portMappings = [{ containerPort = local.container_port, protocol = "tcp" }]
    environment  = [{ name = "PORT", value = tostring(local.container_port) }]
    # 啟動時由 ECS 從 Secrets Manager 取值注入成環境變數；映像檔裡沒有任何密鑰
    secrets = var.use_live_tdx ? local.tdx_secrets : []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "app"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = var.project
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.min_tasks
  launch_type     = "FARGATE"

  health_check_grace_period_seconds  = var.health_check_grace_seconds
  deployment_minimum_healthy_percent = 100 # 新 Task 健康後才停舊的：滾動更新不停機
  deployment_maximum_percent         = 200

  # 新版本一直起不來時自動回滾到上一版
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true # 無 NAT Gateway，靠公有 IP 連外（見 network.tf 取捨說明）
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = local.container_name
    container_port   = local.container_port
  }

  # 首次部署之後，映像版本由 GitHub Actions 更新、Task 數量由 Auto Scaling 調整，
  # Terraform 不要把它們改回去
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  depends_on = [aws_lb_listener_rule.from_cloudfront]
}
