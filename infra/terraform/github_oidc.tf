# GitHub Actions 透過 OIDC 取得臨時憑證（約 1 小時有效），GitHub 上不存任何長期 Access Key。
# 信任條件鎖死：只有指定 repo 的指定分支能扮演這個角色，PR 或 fork 都不行。

locals {
  github_oidc_url = "token.actions.githubusercontent.com"
  github_owner    = split("/", var.github_repo)[0]
  github_reponame = split("/", var.github_repo)[1]
  # 例：lhy4290@155805623/HackRail-TransferPlatform@1314998535
  github_repo_with_ids = "${local.github_owner}@${var.github_owner_id}/${local.github_reponame}@${var.github_repo_id}"
  github_oidc_arn      = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://${local.github_oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://${local.github_oidc_url}"
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
    # GitHub 的 sub 有兩種格式，兩種都完全比對：
    #   舊：repo:owner/repo:ref:refs/heads/master
    #   新：repo:owner@<owner_id>/repo@<repo_id>:ref:refs/heads/master（帶數字 ID，同名新 repo 對不上）
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:sub"
      values = [
        "repo:${var.github_repo}:ref:refs/heads/${var.github_branch}",
        "repo:${local.github_repo_with_ids}:ref:refs/heads/${var.github_branch}",
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${var.project}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"] # 只能是 "*"（AWS 不支援資源層級）
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # Register/DescribeTaskDefinition 不支援資源層級權限，只能是 "*"
  statement {
    sid       = "TaskDefinition"
    actions   = ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"]
    resources = ["*"]
  }

  statement {
    sid       = "UpdateService"
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = [aws_ecs_service.app.id]
  }

  # 註冊新 Task Definition 時要把 Execution Role 交給 ECS，只允許交給 ECS
  statement {
    sid       = "PassExecutionRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.task_execution.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # 部署後清掉 CloudFront 上的舊 index.html
  statement {
    sid       = "InvalidateCdn"
    actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
    resources = [aws_cloudfront_distribution.app.arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy-least-privilege"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
