# 고정 IP를 사용하는 AWS 모의운용 배포

현재는 작성·로컬 검증 단계이며 실제 배포 완료가 아니다. 사용자는 2026-10-14 전체
예상 월 $7~10(세금·크레딧 제외)으로 중계 EC2 1대와 고정 IP 1개를 추가하는 방향을
승인했다. 최초 시작·정지·앱 예약은 모두 꺼 둔다. 실거래와 실계좌 Secret 연결은 금지다.

## 1. 관리자가 네트워크 배포 권한을 한 번 등록

작업 계정에는 기존 Secret 등록·ECR 업로드·네트워크 조회 권한만 있다. 아래 IAM
전용 스택은 관리자 권한이 있는 콘솔에서 등록한다. 작업 계정에 관리자 정책을 붙이거나
CLI에서 root 프로필로 전환하지 않는다.

1. 서울 리전(`ap-northeast-2`)의 **CloudFormation**을 연다.
2. **스택 생성 → 새 리소스 사용(표준)**을 선택한다.
3. **기존 템플릿 선택 → 템플릿 파일 업로드**를 선택한다.
4. 같은 폴더의 `paper-network-iam-bootstrap.yaml`을 업로드한다.
5. 스택 이름은 `stock-automation-paper-network-iam`, 사용자 이름은
   `stock-paper-operator` 그대로 입력한다.
6. 나머지 설정은 기본값을 유지한다. 검토 화면에서 이름이 지정된 IAM 리소스 생성
   안내를 확인하고 생성한다. `CREATE_COMPLETE`를 확인한다.

이 스택은 NAT 호스트의 SSM 역할/프로필, 시작·정지 역할, 네트워크 전용 CloudFormation
서비스 역할, 작업 계정의 관리형 정책을 만든다. EC2·EIP·앱은 아직 만들지 않는다.
배포 역할은 서울의 프로젝트 태그 자원을 관리하고 기존 VPC/공개 서브넷을 참조한다.
`t3.micro`, IMDSv2, 암호화 gp3 8GiB와 지정된 역할 전달만 허용한다. Secret 값 조회와
IAM 편집 권한은 없다. **앱 스택 배포 권한은 별도로 준비·확인할 대상**이다.

이미 이 IAM 스택을 만든 뒤 파일이 갱신됐다면 **기존 IAM 스택 선택 → 업데이트 →
현재 템플릿 교체 → 템플릿 파일 업로드**로 최신 파일을 적용한다. 새 IAM 스택을
같은 역할 이름으로 중복 생성하지 않는다. 2026-10-14 최초 네트워크 실행은 생성 전
가용영역 매개변수 검증의 `ec2:DescribeAvailabilityZones` 누락으로 롤백됐다.
수정본은 이 서울 조회 권한과 지정 네트워크 스택의 정리 권한을 추가한다.
적용 후 실제 생성 자원이 없는 `ROLLBACK_COMPLETE` 네트워크 스택만 확인해
정리한 뒤 새 변경 세트로 재시도한다. IAM 스택과 기존 VPC·Secret·이미지는 보존한다.

## 2. PC-C가 실제 상태를 조회해 매개변수 준비

프로젝트 최상위에서 실행한다. AWS 조회만 하며 자원을 생성하지 않는다.

```powershell
.\.venv\Scripts\python.exe stock-automation/tools/prepare_fixed_egress.py
```

VPC DNS 두 설정, 공개 서브넷의 실제 IGW 경로, 같은 AZ의 새 사설망, Amazon 소유
AL2023 x86_64 AMI와 최소 루트 디스크를 확인한다. 기존 `10.77.0.0/20`과
`10.77.16.0/20`을 피한 첫 /24는 `10.77.32.0/24`다. 실제 조회 결과를 우선한다.
AMI에 8GiB보다 큰 디스크가 필요하면 임의로 늘리지 않고 예산 영향을 다시 검토한다.
결과는 Git 제외 `runtime/paper-network-parameters.json`에 저장한다. 기존 결과는
덮어쓰지 않으므로 검토·별도 보존 후 재생성한다. 식별자·키·원본 로그를 Git에 옮기지 않는다.

## 3. 네트워크 스택 배포와 최초 부팅 확인

PC-C가 매개변수와 `paper-fixed-egress.yaml`, `stock-paper-network-deployer` 역할로
이름이 정확히 `stock-automation-paper-network`인 스택을 만든다. `StartScheduleState=DISABLED`다.
`create-stack` 또는 명시적 `paper-network-*` 변경 세트 이름을 사용한다. 일반
`aws cloudformation deploy`의 자동 변경 세트 이름은 이 제한된 정책 범위에 없다.

새 사설 서브넷 1개, 전용 경로/보안 그룹/인터페이스, NAT EC2 1대, EIP 1개다.
인터페이스에 EIP를 먼저 붙인 뒤 호스트를 부팅한다. NAT에는 앱과 키움 키를 넣지 않는다.
사설망 TCP 443만 전달하고 SSH는 열지 않는다. 앱의 공인 IP 할당은 차단한다.
EC2는 예약 비활성과 별개로 최초 생성 시 부팅하므로 검증 후 즉시 정지한다.
OS 독립 정지 타이머는 패키지 설치 전에 등록하고 매 부팅 2시간 뒤 정지한다.
OS/타이머 장애까지 지출을 강제로 제한하지는 않으므로 실제 EC2 상태를 확인한다.

`CREATE_COMPLETE`만으로 준비 완료를 선언하지 않는다. SSM으로 cloud-init 성공,
IP forwarding, iptables 규칙과 재부팅 후 유지, 정지 타이머 활성 상태를 확인한다.
실제 사설 Fargate 작업의 HTTPS 연결과 관찰된 공인 IP가 EIP와 일치하는지도 확인한다.
실패하면 앱 예약을 켜지 않는다.

## 4. 키움 등록과 앱 온라인 통합검증

새 EIP를 **키움 모의투자 키**의 허용 IP에 등록한다. 기존 PC IP는 등록 한도 내에서 유지한다.
최신 `/tmp` 권한 이미지의 검증된 ECR digest, 사설 서브넷과 기존 작업 보안 그룹을
앱 스택에 전달한다. `AssignPublicIp=DISABLED`, 핵심/NXT 예약 모두 `DISABLED`다.

앱 배포 권한, 확인된 수수료·세금, KRX 전체 휴장일 파일, 실제 Fargate `/tmp` 쓰기,
키움 demo·OpenDART 조회, S3/DynamoDB 원장·멱등성, 텔레그램 전달은 각각 확인할 대상이다.
키·계좌·개인 식별자·응답 원문은 로그/Git에 저장하지 않는다. 앱의 AI 모의체결 기록과
증권사에 제출하는 모의 주문을 구분한다. 현재 앱은 AI 모의체결을 기록한다.

## 5. 검증 완료 후 모의 예약 시작

핵심 앱 예약과 NAT 시작·정지 예약을 함께 활성화한다. NXT/상시 단타는 켜지 않는다.

| NAT 실행 창(KST) | 포함하는 앱 작업 |
|---|---|
| 평일 08:55~09:25 | 09:05 점검, 09:10 청산, 09:15 중기 진입 |
| 평일 14:40~16:10 | 14:50 스캔, 15:10 재검증, 15:20 진입, 15:35/40/50 후속 작업 |
| 토요일 07:50~08:40 | 08:00 주간 튜닝 |

시작은 5분까지만 재시도한다. 실제 부팅·재시도·작업 완료 시간이 창 안에 드는지
검증하기 전에는 다음 거래일 자동 실행을 확정하지 않는다. 정지 전에 실행 중 작업이
없는지 확인한다. 창을 넘는 작업/늦은 재시도는 별도 보완 대상이다.
22거래일·토요일 4회면 NAT 약 47.3시간/월이다. EIP는 정지 중에도 요금이 발생한다.
디스크·기존 Secret/ECR·앱 단기 실행·로그 포함 전체 $7~10은 예상 범위이며 지출 상한은 아니다.

## 로컬 검증

앱 의존성과 분리된 검증 도구 경로를 사용한다.

```powershell
.\.venv\Scripts\python.exe -m pip install --target runtime/infra-validation -r stock-automation/infra/requirements-validation.txt
$env:PYTHONPATH = "runtime/infra-validation"
.\.venv\Scripts\python.exe stock-automation/tools/validate_paper_infrastructure.py
$env:PYTHONPATH = "stock-automation/src"
.\.venv\Scripts\python.exe -m unittest discover -s stock-automation/tests
```

로컬 스키마/IAM/안전 구조 검사이며 AWS 생성이나 SBOM 전송은 없다. 실제 배포·원격
권한·온라인 API 성공은 별도 확인이다.

공식 근거: [NAT 구성](https://docs.aws.amazon.com/vpc/latest/userguide/work-with-nat-instances.html),
[Scheduler API 대상](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html),
[CloudFormation 서비스 역할](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html),
[DynamoDB 거래 IAM](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html),
[공인 IPv4 비용](https://aws.amazon.com/vpc/pricing/).
