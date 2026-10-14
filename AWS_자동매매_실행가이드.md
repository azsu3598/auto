# AWS 자동매매 실행 가이드

## 현재 안전 범위

기본 AWS 스택은 키움 REST **모의투자 조회와 모의체결만** 수행합니다. 수동 실주문
코드 골격은 별도로 존재하지만 모의전략과 연결되어 있지 않고 기본 잠금 상태입니다.
종가배팅·장중 단타·1~2개월 전략의 자금과 원장은 분리되며 최초 배포 시 모든 예약
작업은 비활성화됩니다. NXT는 사용하지 않는 상태를 유지합니다.

## 1. 사전 준비

- Windows에 Docker Desktop과 AWS CLI v2 설치
- AWS CLI 작업용 로그인 확인: `aws sts get-caller-identity --profile stock-paper-operator`
- 키움 모의투자 App Key/Secret, OpenDART API 키 준비
- 텔레그램 봇 토큰과 본인 `chat_id` 준비
- 고정 egress IP를 거치는 사설 서브넷과 인바운드 규칙이 없는 작업 보안 그룹 준비

PC-C에서는 [네트워크 권한·고정 IP 준비](stock-automation/infra/고정IP_모의배포_진행.md)를
먼저 따릅니다. 기존 공개 서브넷을 앱에 넘기지 않습니다. NAT와 앱 시작 예약은
온라인 검증 전까지 비활성으로 유지합니다.

Secrets Manager에 다음 JSON을 각각 저장합니다. 값은 코드, 명령 기록, 로그에 남기지 않습니다.

```json
{"app_key_mock":"...","app_secret_mock":"..."}
{"dart_api_key":"40자리 키"}
{"bot_token":"...","chat_id":"..."}
```

각 Secret ARN을 기록합니다.

## 2. 테스트와 이미지 생성

PowerShell에서 실행합니다.

```powershell
cd C:\Test
$env:AWS_PROFILE = "stock-paper-operator"
$env:PYTHONPATH = "stock-automation/src"
python -m unittest discover -s stock-automation/tests -v

$Region = "ap-northeast-2"
$AccountId = aws sts get-caller-identity --query Account --output text
$Repo = "stock-automation"
$ImageTag = "paper-$(git rev-parse --short HEAD)-$(Get-Date -Format yyyyMMddHHmmss)"
$ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/${Repo}:$ImageTag"

aws ecr describe-repositories --repository-names $Repo --region $Region 2>$null
if ($LASTEXITCODE -ne 0) { aws ecr create-repository --repository-name $Repo --region $Region }
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"
docker build -f stock-automation/Dockerfile -t "${Repo}:$ImageTag" .
docker tag "${Repo}:$ImageTag" $ImageUri
docker push $ImageUri
```

## 3. 스택 최초 배포

수수료와 세금은 실제 키움 계좌 조건을 확인해 basis point 단위로 입력합니다. 예를 들어 0.10%는 10 bps입니다. 임의의 값을 넣지 마세요.

```powershell
$Stack = "stock-automation-paper"
$Subnets = aws cloudformation describe-stacks --region $Region --stack-name stock-automation-paper-network --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnetId'].OutputValue" --output text
$SecurityGroups = "sg-AAAA"
$KiwoomSecretArn = "arn:aws:secretsmanager:..."
$DartSecretArn = "arn:aws:secretsmanager:..."
$TelegramSecretArn = "arn:aws:secretsmanager:..."
$BuyFeeBps = "확인한 값"
$SellFeeBps = "확인한 값"
$SellTaxBps = "확인한 값"

aws cloudformation deploy `
  --region $Region `
  --stack-name $Stack `
  --template-file stock-automation/infra/cloudformation.yaml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    ImageUri=$ImageUri `
    SubnetIds=$Subnets `
    AssignPublicIp=DISABLED `
    SecurityGroupIds=$SecurityGroups `
    KiwoomDemoSecretArn=$KiwoomSecretArn `
    DartSecretArn=$DartSecretArn `
    NotificationChannel=telegram `
    NotificationSecretArn=$TelegramSecretArn `
    BuyFeeBps=$BuyFeeBps `
    SellFeeBps=$SellFeeBps `
    SellTaxBps=$SellTaxBps `
    CoreScheduleState=DISABLED `
    NxtScheduleState=DISABLED
```

## 4. 거래일 파일 등록

한국거래소가 공지한 해당 연도의 전체 휴장일을 정확히 넣고 매년 갱신합니다. 아래는
구조 예시일 뿐이므로 그대로 업로드하지 말고 연도와 날짜를 모두 교체합니다.

```json
{"year":2026,"holidays":["2026-<MM>-<DD>","2026-<MM>-<DD>"]}
```

```powershell
$Bucket = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text
aws s3 cp .\calendar-current.json "s3://$Bucket/config/calendar/current.json" --region $Region
```

## 5. 읽기 전용 온라인 점검

`doctor-overrides.json`을 만듭니다.

```json
{"containerOverrides":[{"name":"stock-automation","command":["doctor","--aws","--online"]}]}
```

```powershell
$Cluster = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='ClusterArn'].OutputValue" --output text
$Task = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='TaskDefinitionArn'].OutputValue" --output text
$LogGroup = aws cloudformation describe-stacks --region $Region --stack-name $Stack --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue" --output text

aws ecs run-task `
  --region $Region `
  --cluster $Cluster `
  --task-definition $Task `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$Subnets],securityGroups=[$SecurityGroups],assignPublicIp=DISABLED}" `
  --overrides file://doctor-overrides.json

aws logs tail $LogGroup --region $Region --since 15m --follow
```

로그의 최종 JSON이 `"ok": true`인지 확인합니다. 이 점검은 종목 목록과 OpenDART 법인코드만 읽으며 주문하지 않습니다.

## 6. 예약 작업 활성화

점검 통과 후 3절의 배포 명령을 다시 실행하되 `CoreScheduleState=ENABLED`로 바꿉니다.
검증된 NAT 시작·정지 예약도 함께 활성화해야 사설 앱이 외부 API에 연결됩니다.
`NxtScheduleState=DISABLED`는 유지합니다.

주요 시간은 KST 기준 14:50 스캔, 15:10 재검증, 15:20 종가배팅 모의진입,
다음 거래일 09:05 점검·09:10 청산입니다. 중기 전략은 15:40 신호, 다음 거래일
09:15 진입 확인, 매일 15:35 재평가합니다. 15:50에는 검증 현재가를 이용해
`EQUITY#PAPER#YYYY-MM-DD` 일일 총자산을 기록합니다.

장중 단타는 예약하지 않습니다. 당일 검증 촉매 파일을 S3에 올린 뒤 KST
09:10~14:50 사이에 ECS 작업의 `RUN_PHASE`를 `DAY_TRADE_ON_DEMAND`로 덮어쓴
경우에만 한 번 실행합니다. 자세한 명령은
[다른 PC 실행방법](C:/Test/다른_PC_프로그램_실행방법.md)의 8.8절을 따릅니다.

이 단발 실행은 완전한 단타 자동매매가 아닙니다. 향후 장중 단타를 실제 기능으로
구현할 때는 08:50~16:00에 EC2 세션을 유지하면서 09:00~15:30을 감시하고,
14:50 신규 진입 중지와 15:10 의무 청산을 수행해야 합니다. 권장 서버, 고정 IP,
API 제한, 월 22,000~27,000원 예상비용과 구현 순서는
[연속 단타 AWS 운영 설계 및 예상비용](C:/Test/docs/프로그램%20설계/연속_단타_AWS_운영설계_및_예상비용.md)을
확인합니다. 이 문서는 향후 구현안이며 현재 배포 명령에 EC2를 추가하지 않습니다.

## 7. 운영 확인과 비상 중지

```powershell
aws logs tail $LogGroup --region $Region --since 1h
aws s3 ls "s3://$Bucket/runs/" --recursive --region $Region
```

이상 동작, 오래된 시세, 거래일 파일 오류, 알림 장애가 보이면 즉시 같은 스택 배포 명령을 `CoreScheduleState=DISABLED`, `NxtScheduleState=DISABLED`로 다시 실행합니다. DynamoDB와 S3에는 `Retain` 정책이 적용되어 스택 삭제 시에도 거래 기록이 보존됩니다.

실주문 전환은 별도 작업입니다. 계좌·주문 권한·체결조회·일손실 한도·중복방지·비상정지 검증과 사용자의 명시적 승인이 끝나기 전에는 절대 활성화하지 않습니다.

## 8. 5거래일 검증과 실거래 판정

PC-C에서 5거래일 동안 CloudWatch, S3, DynamoDB 결과를 확인합니다. 날짜별 작업
성공 여부, 모의 결정·체결·손익, 총자산, 중복 실행, 지갑·포지션 불일치, API 오류를
요약해 `C:\Test\docs\운영 검증\`에 Markdown으로 저장하고 공동 인수인계와 함께
Git에 push합니다. 앱 키, Secret, 토큰, 계좌번호와 원본 로그는 커밋하지 않습니다.

실거래 검토는 다음 조건을 모두 만족한 이후에만 시작합니다.

- 5거래일 모의운용 및 원장 일치
- 주문 취소와 장시간 미체결 처리
- 재시작 후 진행 중 주문 복구
- 주문·체결·잔고 주기적 대사
- 불일치 시 자동 비상정지
- 기존 보유종목 보호와 계좌 지문 확인
- 모의·실거래 AWS 인프라와 Secret 분리
- 사용자 별도 승인

첫 단계는 자동매매가 아니라 사용자가 주문별로 승인하는 극소액 감독형 주문입니다.

## 참고

- [Amazon ECR 이미지 푸시](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html)
- [AWS CLI CloudFormation deploy](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/deploy/index.html)
- [EventBridge Scheduler 일정 관리](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-state.html)
- [ECS에서 Secrets Manager 값 주입](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html)
