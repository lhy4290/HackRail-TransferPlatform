# ALB 只接受 CloudFront 的流量，做兩層檢查：
# 1. Security Group：來源 IP 必須在 CloudFront 回源 IP 清單內（network.tf）
# 2. 自訂標頭：CloudFront 回源時帶 X-Origin-Verify 密值，ALB 比對不符就回 403
#    （第 1 層擋不住「別人自己開的 CloudFront」，第 2 層才擋得住）

resource "random_password" "origin_verify" {
  length  = 32
  special = false
}

resource "aws_lb" "app" {
  name                       = "${var.project}-alb"
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "app" {
  name                 = "${var.project}-tg"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip" # Fargate awsvpc 模式必須用 ip
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "/api/health"
    matcher             = "200"
    interval            = 30
    timeout             = 10 # 需求 9.2：健康檢查 10 秒內回應
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "from_cloudfront" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origin_verify.result]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
