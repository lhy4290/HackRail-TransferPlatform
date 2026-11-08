# 只建立「空的」Secret。憑證值由人在 AWS Console 手動填入，
# 不寫進 Terraform 程式碼，也不會出現在 Terraform state 裡。
# 格式（Key/value）：TDX_CLIENT_ID、TDX_CLIENT_SECRET
resource "aws_secretsmanager_secret" "tdx" {
  name                    = "${var.project}/tdx-credentials"
  description             = "TDX API OAuth client credentials"
  recovery_window_in_days = 0 # demo 環境：destroy 後可立即用同名重建
}
