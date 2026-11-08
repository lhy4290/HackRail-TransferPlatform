terraform {
  required_version = ">= 1.10" # 1.10+ 支援 S3 原生鎖（use_lockfile），不需要 DynamoDB

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # bucket / region 放在 backend.hcl（帳號相關，不進 Git）：
  #   terraform init -backend-config=backend.hcl
  backend "s3" {
    key          = "hackrail/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
