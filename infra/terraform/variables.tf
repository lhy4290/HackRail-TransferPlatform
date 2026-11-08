variable "aws_region" {
  description = "部署區域。台北 ap-east-2 若缺服務，改成東京 ap-northeast-1"
  type        = string
  default     = "ap-east-2"
}

variable "project" {
  description = "所有資源名稱的前綴"
  type        = string
  default     = "hackrail"
}

variable "image_tag" {
  description = "第一次部署用的映像標籤（git commit SHA）。之後由 GitHub Actions 更新，Terraform 不再管"
  type        = string
}

variable "use_live_tdx" {
  description = "true：從 Secrets Manager 注入 TDX 憑證（真實模式）；false：不給憑證，容器以 Demo 快照啟動"
  type        = bool
  default     = true
}

variable "task_cpu" {
  description = "Fargate vCPU 單位（512 = 0.5 vCPU）"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate 記憶體（MiB）"
  type        = number
  default     = 1024
}

variable "min_tasks" {
  type    = number
  default = 1
}

variable "max_tasks" {
  type    = number
  default = 2
}

variable "health_check_grace_seconds" {
  description = "Task 啟動後多久才開始算 ALB 健康檢查。本機實測真實模式遇到 TDX 429 限流時啟動約 185 秒，留緩衝"
  type        = number
  default     = 300
}

variable "alert_email" {
  description = "告警通知 Email（留空則不建立訂閱）"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "允許部署的 GitHub repo（owner/name）"
  type        = string
  default     = "lhy4290/HackRail-TransferPlatform"
}

variable "github_owner_id" {
  description = "GitHub 帳號的數字 ID（新版 OIDC sub 會帶 owner@id/repo@id，防 repo 改名後被同名 repo 冒用）"
  type        = string
  default     = "155805623"
}

variable "github_repo_id" {
  description = "GitHub repo 的數字 ID"
  type        = string
  default     = "1314998535"
}

variable "github_branch" {
  description = "只有這個分支的 workflow 能取得部署角色"
  type        = string
  default     = "master"
}

variable "create_github_oidc_provider" {
  description = "帳號裡已經有 token.actions.githubusercontent.com 的 OIDC provider 時設成 false"
  type        = bool
  default     = true
}
