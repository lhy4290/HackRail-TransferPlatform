# 部署手冊（AWS ECS Fargate + Terraform）

指令都在 **PowerShell** 執行，從 repo 根目錄開始。架構說明見 [docs/cloud-architecture.md](../docs/cloud-architecture.md)。

## 資料夾

| 路徑 | 內容 |
|---|---|
| `infra/bootstrap/` | 一次性：存 Terraform state 的 S3 bucket（本身用本機 state） |
| `infra/terraform/` | 主體：VPC、ECR、Secrets Manager、IAM、ALB、ECS、CloudFront、CloudWatch、Auto Scaling、GitHub OIDC |
| `.github/workflows/ci.yml` | PR：pytest、前端 tsc＋vitest＋build、terraform fmt/validate、Docker build＋Trivy |
| `.github/workflows/deploy.yml` | push 到 `master`：先跑 CI → OIDC 登入 → 推 ECR → 更新 ECS → 清 CloudFront → smoke test |

## 0. 前置

- AWS CLI、Terraform ≥ 1.10、Docker Desktop 已安裝，`aws sts get-caller-identity` 能回傳你的 IAM 使用者
- 用台北區域（ap-east-2）的話，要先在 AWS Console → 帳號 → AWS 區域 **啟用** 這個區域（新區域預設關閉）

## 1. 本機驗證容器

```powershell
docker build -t hackrail .
docker run --rm -p 8000:8000 hackrail                            # Demo 模式
docker run --rm -p 8000:8000 --env-file backend/.env hackrail     # 真實 TDX 模式
curl.exe -i http://localhost:8000/api/health
docker stats --no-stream                                          # 記下記憶體用量
```

記下真實模式從啟動到 `Application startup complete` 花多久（實測：Demo 2 秒；真實模式順利時約 16 秒，遇到 TDX 429 限流重試時約 185 秒；記憶體約 60 MB）。`health_check_grace_seconds` 預設 300 秒，必須大於這個時間。

## 2. Bootstrap（state bucket）

```powershell
cd infra/bootstrap
terraform init
terraform apply
terraform output -raw backend_hcl | Out-File -Encoding ascii ../terraform/backend.hcl
cd ../terraform
```

## 3. 先建 ECR 和 Secret

ECS 啟動時要拉映像、讀 Secret，所以這兩個要先建好、先放內容。

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars   # 填 alert_email，image_tag 先不管
terraform init -backend-config=backend.hcl
terraform apply -target="aws_ecr_repository.app" -target="aws_ecr_lifecycle_policy.app" -target="aws_secretsmanager_secret.tdx"
```

**填 TDX 憑證**：AWS Console → Secrets Manager → `hackrail/tdx-credentials` → 擷取秘密值 → 設定秘密值 → Key/value 填兩組：`TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`。（用 Console 填，憑證就不會留在終端機歷史紀錄裡。）

## 4. 推第一版映像

```powershell
$REGION = "ap-east-2"
$REPO   = terraform output -raw ecr_repository_url
$TAG    = git rev-parse HEAD
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REPO.Split('/')[0]
docker build -t "${REPO}:${TAG}" ../..
docker push "${REPO}:${TAG}"
echo $TAG    # 把這個值填到 terraform.tfvars 的 image_tag
```

## 5. 建立其餘資源

```powershell
terraform apply        # CloudFront 建立約需 5–10 分鐘
terraform output
```

- 收信並點 SNS 訂閱確認連結
- 打開 `app_url`，查一條路線
- 直接連 `http://<alb_dns_name>` 應該回 **403**（證明只能從 CloudFront 進來）
- 確認是真實模式：`aws logs tail /ecs/hackrail --since 15m`，應看到「使用 TDX 真實資料啟動」，而不是「使用 Demo 快照啟動」或「TDX 資料匯入失敗」
- 測告警：`aws cloudwatch set-alarm-state --alarm-name hackrail-unhealthy-hosts --state-value ALARM --state-reason "test"`，確認收到信

## 6. 設定 GitHub

`terraform output github_variables` 的每一項，填到 repo → Settings → Secrets and variables → Actions → **Variables**（不是 Secrets，這些都不是機密）。

分支保護：Settings → Branches → `master` → Require a pull request + Require status checks（勾 CI 的 4 個 job）。

之後開 PR → CI 綠燈 → merge → `deploy.yml` 自動部署。

## 7. 示範自動回滾（選做）

開一個 PR，讓容器啟動就失敗（例如 Dockerfile 的 `CMD` 改成不存在的模組），merge 後 ECS Circuit Breaker 會偵測新 Task 一直起不來並自動回到上一版，`deploy.yml` 的「Deploy to ECS」步驟會顯示失敗。截圖後 revert。

## 8. 清除

```powershell
cd infra/terraform
terraform destroy
```

state bucket 保留不影響費用（幾 KB）；要刪的話先在 Console 清空 bucket（含所有版本），再到 `infra/bootstrap` 跑 `terraform destroy`。

## 費用估算（ap-east-2，每月，1 個 Task 常駐）

ALB 約 USD 18、Fargate 0.5 vCPU/1 GB 約 USD 18、公有 IPv4 位址（ALB×2＋Task×1）約 USD 11、Secrets Manager USD 0.4，其餘（CloudFront、ECR、CloudWatch）在免費額度內。合計約 **USD 45–50／月**，只開幾天約 USD 5。
