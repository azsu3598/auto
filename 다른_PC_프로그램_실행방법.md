# 다른 PC에서 자동매매 프로그램 실행하기

## 현재 상태

이 문서는 다른 Windows PC로 개발 환경을 옮기기 위한 사전 가이드입니다.

- 모의 종가배팅·중기 전략·텔레그램 알림·AWS 예약 실행은 구현되어 있습니다.
- 실제 주문 기능은 개발 중이며 기본적으로 비활성화되어 있습니다.
- `LIVE_ORDER_ENABLED=1`을 임의로 설정하지 마세요.
- 실제 계좌 연결은 주문·체결 통합 테스트와 최종 안전 점검 후 별도로 진행합니다.

## 1. 필요한 프로그램

새 PC에 다음 항목을 설치합니다.

1. Git
2. Python 3.13 이상
3. Docker Desktop(WSL2 백엔드 사용)
4. AWS CLI v2
5. Visual Studio Code와 WSL 확장(선택)

설치 확인:

```powershell
git --version
py -3.13 --version
docker --version
aws --version
```

## 2. 폴더 배치

프로그램은 다음 구조를 전제로 합니다.

```text
D:\Test\
├─ stock-automation\
├─ Kiwoom-REST-API\
├─ AWS_자동매매_실행가이드.md
└─ 다른_PC_프로그램_실행방법.md
```

`stock-automation` 폴더와 두 가이드 파일은 USB, 개인 클라우드 또는 비공개 Git
저장소로 복사합니다. API 키, 토큰, `.env` 파일은 복사본에 포함하지 않습니다.

키움 공식 라이브러리는 새 PC에서 다시 받습니다.

```powershell
New-Item -ItemType Directory -Force D:\Test
cd D:\Test
git clone https://github.com/Kiwoom-Securities/Kiwoom-REST-API.git
git -C Kiwoom-REST-API checkout 234560d213acd8871ae344b5481aecd2f30287fa
```

위 커밋은 현재 프로그램이 명세 검증에 사용한 버전입니다. 임의로 최신 버전으로
올리기 전에 전체 테스트를 다시 통과시켜야 합니다.

## 3. 로컬 Python 환경 구성

```powershell
cd D:\Test
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install .\Kiwoom-REST-API .\stock-automation
stock-automation --help
```

PowerShell 실행 정책 때문에 가상환경 활성화가 차단되면 현재 창에서만 다음 명령을
먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 4. 이전 직후 검증

```powershell
cd D:\Test\stock-automation
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

테스트가 하나라도 실패하면 AWS 배포나 실제 주문 명령을 실행하지 않습니다.

## 5. 키움 모의투자 연결

로컬 PC에서는 키움 라이브러리의 설정 명령으로 모의투자 키를 OS 자격증명 저장소에
등록하는 방식을 우선 사용합니다.

```powershell
kiwoomcli setup
```

설정할 때 `demo` 또는 모의투자 계정을 선택합니다. 키를 코드, Markdown, Git,
PowerShell 스크립트에 직접 적지 않습니다.

```powershell
$env:KIWOOM_MODE = "demo"
$env:KIWOOM_TOKEN_STORE = "memory"
stock-automation doctor --online
```

OpenDART 온라인 점검에는 별도 API 키가 필요합니다. AWS에서는 반드시 Secrets
Manager로 주입하며, 로컬 셸 기록에 키를 남기지 않는 것이 원칙입니다.

## 6. 로컬 모의분석 실행

저장된 예제 스냅샷으로 주문 없이 분석 엔진을 확인합니다.

```powershell
cd D:\Test\stock-automation
New-Item -ItemType Directory -Force runtime\reports
stock-automation analyze `
  --snapshot examples\krx_snapshot.json `
  --ledger runtime\paper-ledger.jsonl `
  --cash 600000 `
  --report-dir runtime\reports `
  --training-events runtime\recommendation-events.csv
```

이 명령은 키움에 실제 주문을 보내지 않습니다.

## 7. Docker 이미지 확인

Docker 빌드는 반드시 `D:\Test`를 컨텍스트로 사용합니다.

```powershell
cd D:\Test
docker build -f stock-automation\Dockerfile -t stock-automation:dev .
docker image inspect stock-automation:dev
```

## 8. AWS에서 실행

### 8.1 AWS 로그인과 리전 확인

개인 Access Key를 파일에 복사하는 방식보다 AWS IAM Identity Center 로그인을
권장합니다. 조직에서 제공한 시작 URL과 리전을 사용합니다.

```powershell
aws configure sso
aws sso login
aws sts get-caller-identity
aws configure get region
```

개인 AWS 계정이고 SSO를 사용하지 않는 경우에만 `aws configure`를 사용합니다.
출력된 AWS 계정이 실제 배포 대상인지 반드시 확인합니다.

```powershell
$Region = "ap-northeast-2"
$AccountId = aws sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0) { throw "AWS 로그인이 필요합니다." }
```

### 8.2 네트워크 준비

초기 구성은 ECS Fargate가 외부 키움·OpenDART·텔레그램 HTTPS API를 호출합니다.
다음을 AWS 콘솔에서 준비합니다.

- 동일 VPC의 공개 서브넷 2개
- 인터넷 게이트웨이로 연결된 라우팅
- 인바운드 규칙이 없는 보안 그룹
- 아웃바운드 TCP 443 허용

사설 서브넷을 사용하려면 NAT Gateway가 별도로 필요합니다. 서브넷 ID와 보안 그룹
ID를 기록합니다.

### 8.3 Secrets Manager 등록

AWS Secrets Manager 콘솔에서 다음 Secret 세 개를 생성합니다. 비밀값을 PowerShell
명령이나 Markdown에 직접 입력하지 않습니다.

키움 모의투자 Secret:

```json
{"app_key_mock":"키움 모의 App Key","app_secret_mock":"키움 모의 Secret Key"}
```

OpenDART Secret:

```json
{"dart_api_key":"40자리 OpenDART 키"}
```

텔레그램 Secret:

```json
{"bot_token":"텔레그램 봇 토큰","chat_id":"본인 채팅 ID"}
```

세 Secret의 ARN을 기록합니다. 실계좌 App Key는 이 모의투자 Secret에 넣지 않습니다.

### 8.4 ECR 생성과 이미지 업로드

```powershell
cd D:\Test
$Repo = "stock-automation"
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$ImageUri = "${Registry}/${Repo}:latest"

aws ecr describe-repositories --repository-names $Repo --region $Region 2>$null
if ($LASTEXITCODE -ne 0) {
  aws ecr create-repository --repository-name $Repo --region $Region
}

aws ecr get-login-password --region $Region |
  docker login --username AWS --password-stdin $Registry

docker build -f stock-automation\Dockerfile -t "${Repo}:latest" .
if ($LASTEXITCODE -ne 0) { throw "Docker 이미지 빌드 실패" }

docker tag "${Repo}:latest" $ImageUri
docker push $ImageUri
if ($LASTEXITCODE -ne 0) { throw "ECR 이미지 업로드 실패" }
```

### 8.5 CloudFormation 최초 배포

최초에는 모든 예약을 비활성화합니다. 수수료와 세금은 키움 계좌에 실제 적용되는
값을 확인한 뒤 basis point 단위로 입력합니다. `10 bps = 0.10%`입니다.

```powershell
$Stack = "stock-automation-paper"
$Subnets = Read-Host "공개 서브넷 ID 두 개를 쉼표로 입력"
$SecurityGroups = Read-Host "보안 그룹 ID 입력"
$KiwoomSecretArn = Read-Host "키움 모의투자 Secret ARN"
$DartSecretArn = Read-Host "OpenDART Secret ARN"
$TelegramSecretArn = Read-Host "텔레그램 Secret ARN"
$BuyFeeBps = Read-Host "검증한 매수 수수료 bps"
$SellFeeBps = Read-Host "검증한 매도 수수료 bps"
$SellTaxBps = Read-Host "검증한 매도 세금 bps"

$DeployParameters = @(
  "ImageUri=$ImageUri",
  "SubnetIds=$Subnets",
  "SecurityGroupIds=$SecurityGroups",
  "KiwoomDemoSecretArn=$KiwoomSecretArn",
  "DartSecretArn=$DartSecretArn",
  "NotificationChannel=telegram",
  "NotificationSecretArn=$TelegramSecretArn",
  "BuyFeeBps=$BuyFeeBps",
  "SellFeeBps=$SellFeeBps",
  "SellTaxBps=$SellTaxBps",
  "CoreScheduleState=DISABLED",
  "NxtScheduleState=DISABLED"
)

aws cloudformation deploy `
  --region $Region `
  --stack-name $Stack `
  --template-file stock-automation\infra\cloudformation.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides $DeployParameters

if ($LASTEXITCODE -ne 0) { throw "CloudFormation 배포 실패" }
```

### 8.6 거래일 파일 업로드

한국거래소가 발표한 운영 연도의 전체 휴장일을 넣습니다. 아래 `<MM>`과 `<DD>`를
실제 값으로 모두 교체하기 전에는 업로드하지 않습니다.

```json
{"year":2026,"holidays":["2026-<MM>-<DD>","2026-<MM>-<DD>"]}
```

파일명을 `D:\Test\calendar-current.json`으로 저장한 후 실행합니다.

```powershell
$Bucket = aws cloudformation describe-stacks `
  --region $Region `
  --stack-name $Stack `
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" `
  --output text

aws s3 cp D:\Test\calendar-current.json `
  "s3://$Bucket/config/calendar/current.json" `
  --region $Region
```

### 8.7 AWS 온라인 진단 실행

`D:\Test\doctor-overrides.json` 파일을 만듭니다.

```json
{"containerOverrides":[{"name":"stock-automation","command":["doctor","--aws","--online"]}]}
```

스택 출력값을 읽고 Fargate 진단 작업을 한 번 실행합니다.

```powershell
$Cluster = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='ClusterArn'].OutputValue" --output text
$Task = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='TaskDefinitionArn'].OutputValue" --output text
$LogGroup = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue" --output text

aws ecs run-task `
  --region $Region `
  --cluster $Cluster `
  --task-definition $Task `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$Subnets],securityGroups=[$SecurityGroups],assignPublicIp=ENABLED}" `
  --overrides file://D:/Test/doctor-overrides.json

aws logs tail $LogGroup --region $Region --since 15m --follow
```

진단 로그의 최종 JSON에서 `"ok": true`를 확인합니다. 실패한 상태에서 예약을
활성화하지 않습니다. 이 진단은 읽기 전용이며 실제 주문을 보내지 않습니다.

### 8.8 예약 작업 활성화

진단이 성공한 경우에만 파라미터 배열의 핵심 예약 상태를 변경하고 같은 스택을
갱신합니다.

```powershell
$DeployParameters = $DeployParameters | ForEach-Object {
  if ($_ -eq "CoreScheduleState=DISABLED") { "CoreScheduleState=ENABLED" } else { $_ }
}

aws cloudformation deploy `
  --region $Region `
  --stack-name $Stack `
  --template-file stock-automation\infra\cloudformation.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides $DeployParameters
```

NXT는 별도 검증 전까지 `NxtScheduleState=DISABLED`로 유지합니다.

활성화되는 주요 KST 작업은 다음과 같습니다.

- 14:50: 종가배팅 전체 후보 스캔
- 15:10: 차트 후보 축소
- 15:20: 최신 가격 재검증 후 모의매수 또는 `NO_TRADE`
- 다음 거래일 09:05: 손절·목표가 조기 점검
- 다음 거래일 09:10: 남은 수량 모의청산
- 15:35: 중기 보유종목 재검토
- 15:40: 1~2개월 전략 신규 신호
- 다음 거래일 09:15: 중기 신호 모의진입 확인
- 토요일 08:00: 기록 기반 규칙 검증 및 모의전략 개선

### 8.9 실행 결과 확인

```powershell
aws logs tail $LogGroup --region $Region --since 1h
aws s3 ls "s3://$Bucket/runs/" --recursive --region $Region

$PaperTable = aws cloudformation describe-stacks `
  --region $Region `
  --stack-name $Stack `
  --query "Stacks[0].Outputs[?OutputKey=='PaperTableName'].OutputValue" `
  --output text

aws dynamodb scan --region $Region --table-name $PaperTable --max-items 20
```

텔레그램에서 `[모의매수]`, 익절, 손절 또는 전략 승격 알림이 도착하는지도
확인합니다.

### 8.10 긴급 중지

오래된 시세, 중복 기록, 비정상 알림 또는 예상하지 못한 비용이 보이면 예약을 즉시
다시 비활성화합니다.

```powershell
$DeployParameters = $DeployParameters | ForEach-Object {
  if ($_ -eq "CoreScheduleState=ENABLED") { "CoreScheduleState=DISABLED" } else { $_ }
}

aws cloudformation deploy `
  --region $Region `
  --stack-name $Stack `
  --template-file stock-automation\infra\cloudformation.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides $DeployParameters
```

스케줄을 꺼도 S3와 DynamoDB 기록은 보존됩니다. 비용 확인을 위해 AWS Budgets에서
월간 예산 알림도 설정합니다.

더 상세한 배포 설명은 [AWS 자동매매 실행 가이드](D:/Test/AWS_자동매매_실행가이드.md)에도
정리되어 있습니다.

## 9. 텔레그램 알림

기존 봇을 계속 사용할 경우 봇 토큰을 파일로 옮기지 말고 새 PC 또는 AWS에서
Secrets Manager를 통해 다시 연결합니다. 토큰 노출이 의심되면 `@BotFather`에서
즉시 재발급합니다. 이메일 알림 기능은 보조 수단으로 그대로 유지됩니다.

## 10. 실제 주문 기능 주의사항

현재 작성된 실제 주문 명령은 다음과 같습니다.

```text
stock-automation live-prepare
stock-automation live-approve
stock-automation live-execute
stock-automation live-kill-switch
```

이 명령들은 아직 새 PC에서 실행하지 않습니다. 실제 주문을 사용하려면 다음 작업이
먼저 완료되어야 합니다.

- 키움 모의계좌 주문·부분체결·미체결 통합 테스트
- 실제 주문 전용 DynamoDB와 실계좌 Secret 분리
- 계좌 별칭, 주문당 최대금액, 총노출, 일손실 한도 확정
- 텔레그램 주문 접수·체결·실패 알림 검증
- 비상정지 기본 `ON` 확인
- 사용자 최종 승인 후에만 실계좌 키 연결

실제 주문 응답이 불명확하면 프로그램은 `UNCERTAIN`으로 잠그며 자동 재주문하지
않습니다. 키움 주문내역을 직접 확인하기 전에는 해당 주문을 다시 실행하면 안 됩니다.

## 이전 완료 체크리스트

- [ ] 두 프로젝트가 `D:\Test` 아래에 나란히 있음
- [ ] 키움 저장소가 지정 커밋을 사용함
- [ ] Python 전체 테스트 통과
- [ ] Docker 이미지 빌드 성공
- [ ] AWS 로그인 계정과 리전 확인
- [ ] 비밀값이 Git이나 복사 파일에 없음
- [ ] 최초 AWS 스케줄이 비활성 상태임
- [ ] 텔레그램 시험 알림 수신
- [ ] 모의투자 온라인 점검 성공
- [ ] 실제 주문 비상정지가 `ON`임
