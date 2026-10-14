# Stock Automation Codex 세션 간 공동 인수인계

> 목적: 회사 PC의 Codex와 집 PC의 Codex가 같은 프로젝트를 번갈아 작업할 때 변경
> 내용, 검증 결과, 남은 위험과 다음 작업을 정확하게 전달한다.  
> PC-D 프로젝트 경로: `D:/Test/stock-automation`
> PC-C 프로젝트 경로: `C:/Test/stock-automation`
> 최초 작성일: 2026-10-12 KST

## 0. PC alias와 경로

| alias | 구분 | 워크스페이스 | 주요 역할 |
|---|---|---|---|
| `PC-D` | 현재 PC | `D:/Test` | 코드·문서·설계·인수인계 |
| `PC-C` | 타 PC | `C:/Test` | 실행·Docker·키움 모의·AWS |

모든 새 `세션 전달 기록` 제목에 작업한 PC alias를 반드시 기록한다.
경로는 문서의 PC별 경로를 따르고, 코드에 `C:` 또는 `D:` 절대경로를
하드코딩하지 않는다. alias 도입 전 기록의 `현재/회사 PC`는 `PC-D`,
`다른/집 PC`는 `PC-C`로 해석한다.

## 1. 사용 규칙

각 Codex는 작업을 시작할 때 이 문서를 먼저 읽고 실제 프로젝트 파일과 비교한다.
문서만 믿지 말고 코드와 테스트로 다시 확인한다.

작업을 마칠 때는 아래 `세션 전달 기록` 맨 위에 새로운 기록을 추가한다. 기존 기록은
삭제하거나 고치지 않는다. 잘못된 기록이 있으면 새 기록에서 정정한다.

**사용자 상시 요청:** 코드·문서 작업이 끝난 모든 세션은 사용자의 추가 요청을
기다리지 말고 이 문서의 `세션 전달 기록` 맨 위에 결과를 기록한다.

반드시 기록할 내용:

- 작업한 PC 또는 환경
- 작업 날짜와 종료시각
- 사용자가 요청한 목표
- 실제 변경 파일
- 구현한 기능
- 실행한 테스트와 결과
- 실패했거나 확인하지 못한 사항
- 남아 있는 위험
- 다음 Codex가 가장 먼저 할 일
- 실거래 활성화 여부

절대로 기록하지 않을 내용:

- 키움 App Key와 Secret
- AWS Access Key와 Secret Key
- AWS 로그인 토큰
- 실제 계좌번호와 비밀번호
- 텔레그램 bot token과 chat ID
- OpenDART API 키
- 개인 이메일·전화번호 등 개인정보

비밀값은 이 문서, 코드, Git, ZIP, GPT 대화에 넣지 않는다.

## 2. 작업 권한 경계

현재 허용된 작업:

- 코드 분석과 수정
- 로컬 테스트
- 가짜 키움 응답을 이용한 주문·체결 테스트
- 모의투자 연결과 AWS 모의환경 준비
- 실거래 안전 기능 개발
- 실거래용 인프라 템플릿 작성
- SABU Trading Console 개선

현재 허용되지 않은 작업:

- 실제 키움 계좌 주문 제출
- 실제 보유종목 매수·매도
- `LIVE_ORDER_ENABLED=1` 설정
- 비상정지 해제
- AWS 실거래 예약 활성화
- 실제 계좌 Secret 연결
- 사용자 확인 없는 비용 발생 배포

실제 주문은 안전 기능·통합 테스트·소액 검증 계획이 완성된 뒤 사용자가 별도로 명시적
승인할 때만 가능하다.

## 3. 공통 기준 문서

새 Codex는 다음 문서를 우선순위대로 확인한다.

1. `<WORKSPACE>/AGENTS.md`
2. `PC-C_단독진행_전체인수인계.md`
3. `<WORKSPACE>/stock-automation/README.md`
4. 이 문서 `Codex_세션간_공동_인수인계.md`
5. `주식_자동매매_사용자_준비_가이드.md`
6. `실거래_개발_후속_Codex_프롬프트.md`
7. `집에_가져갈_주식자동매매_파일목록.md`
8. `Codex_슬래시_명령어_최신가이드.md`
9. `<WORKSPACE>/docs/프로그램 설계/`의 설계 문서

내용이 충돌하면 실제 코드와 `AGENTS.md`를 기준으로 판단하고 충돌 사실을 사용자에게
알린다.

## 4. 프로젝트 폴더 구조

```text
<WORKSPACE>/
├─ AGENTS.md
├─ Codex_슬래시_명령어_최신가이드.md
├─ .dockerignore
├─ stock-automation/
└─ Kiwoom-REST-API/
```

`stock-automation`과 `Kiwoom-REST-API`는 형제 폴더여야 한다. Docker 빌드는
PC-D는 `D:/Test`, PC-C는 `C:/Test`를 Docker 빌드 컨텍스트로 사용한다.

## 4-1. PC별 역할

### PC-D(현재 PC)

- 코드 검토와 설계 논의
- Markdown 문서와 인수인계 관리
- 안전규칙 검토
- 실행 결과 분석
- 실행할 수 없는 명령을 실행했다고 주장하지 않음

현재 PC는 프로그램 실행 환경으로 사용하지 않는다. 이 PC에서 테스트·Docker·AWS
명령을 실행할 수 없는 경우 결과를 추측하지 않고 `미실행`으로 기록한다.

### PC-C(타 PC)

- Python 전체 테스트의 기준 환경
- Docker 이미지 빌드와 로컬 UI 실행
- 키움 모의 API 읽기 연결검사
- AWS CLI 로그인과 AWS 모의환경 배포
- CloudWatch·S3·DynamoDB·텔레그램 통합검증
- 향후 실거래 안전 기능의 테스트 환경

실행 성공 여부는 다른 PC의 실제 명령 출력으로만 확정한다. 다른 PC에서 실행한
명령·결과·시각을 세션 전달 기록에 남긴다. API 키와 계좌정보는 기록하지 않는다.

### 전달 원칙

- 현재 PC에서 수정한 코드는 다른 PC에서 전체 테스트를 통과해야 완료로 확정한다.
- 다른 PC에서 변경한 코드는 프로젝트 파일과 공동 인수인계를 함께 현재 PC로 가져온다.
- 두 PC의 파일이 다르면 최신 수정시각만 보고 덮어쓰지 않고 차이를 비교한다.
- AWS와 실행 상태의 최종 근거는 다른 PC의 실제 로그다.

## 5. 현재 공통 기준 상태

2026-10-12 문서 작성 시점 기준이며 새 세션에서 반드시 재검증한다.

### 구현된 항목

- 종가배팅 분석·모의매매 엔진
- KRX 14:50, 15:10, 15:20 예약 단계
- 다음 거래일 09:05 점검과 09:10 잔여 수량 청산
- NXT 가능 종목의 KRX 종가배팅 제외
- 비상 손절 기준 최대 계획손실 계산
- 검증된 당일 촉매 필수 필터
- 5분봉 확인 손절
- S3·DynamoDB·텔레그램을 사용하는 AWS 모의 구조
- 중기전략과 종가배팅 자금·원장 분리
- 종목별 코스피·코스닥 약세 감점·그룹 급락 진입 차단
- 키움 당일 기관·프로그램 수급 연동(외국인 미사용)
- 종가배팅·중기와 분리된 `DAY_TRADE` 단타 기본 모의엔진
- 수동 실주문 CLI 골격
- 주문내용 해시·승인 유효시간·중복 제출 방지 골격
- 키움 실계좌 지문 고정과 기존 키움 보유수량의 1회성 보호 기준선 골격
- 키움 주문번호별 부분체결·완전체결·취소·거부 상태 분류
- 누적 체결량 증가분만 원자적으로 반영하는 프로그램 보유수량 원장
- 키움 읽기 API를 사용하는 단타 단발 모의 스캔과 대시보드 전략 구분 표시
- 전략별 모의·실거래 독립 다중선택 UI와 DynamoDB 설정 형식(현재 변경 잠금)
- 모의·실거래를 분리한 일별 총자산 추이 그래프와 `EQUITY#<MODE>#<날짜>` 형식
- 최근 매수·매도·NO_TRADE의 판단 근거를 한글로 표시하는 UI
- 단타 단발 AWS 실행의 S3·DynamoDB 저장 경로(자동 반복 스케줄 없음)
- 거래일 15:50 일일 총자산 집계 작업과 기본 비활성 AWS 예약 템플릿
- `SABU Trading Console` PC·모바일 읽기 전용 UI
- UI의 실거래 준비상태 `안전조건 미충족` 잠금

### 마지막으로 확인된 테스트

```text
전체 단위 테스트: 132개 통과
Python compileall: 통과
JavaScript 문법검사: 통과
PC·모바일 브라우저 렌더링: 확인
```

테스트 명령:

```powershell
Set-Location <PC별 stock-automation 경로>
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

### 아직 완료되지 않은 항목

- 키움 주문 취소 요청 API와 장시간 미체결 자동 처리
- 키움 주문·체결·잔고 대사의 실제 모의/실계좌 통합검증
- 재시작 후 진행 중 주문 복구
- 계좌 지문 고정의 실제 키움 계좌 통합검증
- 불일치 자동 비상정지
- 실거래 전용 AWS 인프라 분리
- 촉매 자동수집
- AWS 모의환경 실제 배포와 5거래일 통합검증
- Cognito·HTTPS가 적용된 대시보드 인터넷 배포
- 대시보드의 실제 AWS 예약 상태와 CloudWatch 오류 연동
- Cognito 인증 기반 실행모드 설정 저장 API와 실제 런타임 모드 라우팅
- 일일 총자산 집계 작업의 실제 키움 현재가·DynamoDB 통합검증
- 단타 단발 AWS 실행의 실제 S3·DynamoDB·대시보드 통합검증
- 단타 AWS 실행은 현재 방침상 상시감시·반복 스케줄 없이 단발 실행만 유지

## 6. 우선 작업 순서

1. 현재 프로젝트 파일 누락 확인
2. 기존 테스트 전부 실행
3. 실거래 코드 위험 감사
4. 계좌 고정과 기존 보유종목 보호 구현
5. 프로그램 체결수량 전용 원장 구현
6. 주문 상태 머신과 부분체결·취소 구현
7. 키움 잔고 대사와 비상정지 구현
8. 대시보드 안전상태 연동
9. 모의·실거래 인프라 분리 템플릿 작성
10. 전체 테스트와 문서 갱신
11. AWS 모의배포
12. 거래일 5일 이상 모의운용

실거래 활성화는 위 작업과 별개의 사용자 승인 단계다.

## 7. 세션 시작 체크리스트

새 Codex는 작업 전에 다음을 확인한다.

- [ ] `AGENTS.md`를 읽었다.
- [ ] 이 공동 인수인계의 최신 기록을 읽었다.
- [ ] 현재 PC의 프로젝트 파일을 직접 확인했다.
- [ ] `stock-automation`과 `Kiwoom-REST-API`가 함께 있다.
- [ ] 기존 테스트를 실행했다.
- [ ] Git 또는 파일 변경 상태를 확인했다.
- [ ] 이전 PC의 미완성 변경이 있는지 확인했다.
- [ ] 실제 주문과 실계좌 연결이 비활성화되어 있다.
- [ ] 이번 세션의 작업 범위를 사용자에게 짧게 알렸다.

## 8. 세션 종료 체크리스트

- [ ] 변경한 파일을 모두 기록했다.
- [ ] 새 기능의 테스트를 추가했다.
- [ ] 기존 전체 테스트를 다시 실행했다.
- [ ] 실패한 테스트를 숨기지 않았다.
- [ ] 실제 주문을 실행하지 않았음을 확인했다.
- [ ] 실거래 잠금 상태를 확인했다.
- [ ] 남은 위험을 기록했다.
- [ ] 다음 Codex가 처음 할 작업을 한 문장으로 기록했다.
- [ ] 아래 전달 기록에 새 항목을 추가했다.
- [ ] 프로젝트와 이 문서를 함께 다음 PC로 복사했다.

## 9. 세션 전달 기록 작성 양식

새 기록을 이 섹션 바로 아래, 가장 위에 추가한다.

```markdown
### YYYY-MM-DD HH:MM KST — [작업 PC alias] → [다음 PC alias]

- 작업 PC alias: `PC-D` 또는 `PC-C`
- 작업 경로:
- 요청 목표:
- 완료한 작업:
- 변경 파일:
  - `경로`
- 추가·변경 테스트:
- 전체 테스트 결과:
- 수동 검증 결과:
- 실패·미확인 사항:
- 남은 위험:
- 실거래 상태: `비활성화 / 비상정지 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업:
- 사용자에게 확인받을 사항:
- 전달 파일 버전 또는 복사시각:
```

## 10. 세션 전달 기록

### 2026-10-14 23:15 KST — PC-C / 네트워크 최초 배포 검증·누락 조회 권한 보완

- 작업 PC alias: `PC-C`, 기준 브랜치 `main` / `7ac8fc6`. 사용자가 관리자 콘솔에서 IAM bootstrap 생성 완료를 보고했다. 세 인수인계를 순서대로 재검토했고 worktree clean이었다. 작업 계정의 실제 새 권한으로 준비 도구가 성공했다. 기존 미커밋/다른 PC 변경을 덮어쓰거나 pull하지 않았다.
- 실제 조회 성공: 지정 작업 사용자 STS 확인, VPC DNS 지원/호스트 이름 설정 모두 true, 기존 공개 서브넷의 실제 IGW 경로와 같은 AZ, 겹치지 않는 사설 `10.77.32.0/24`, Amazon 소유 최신 AL2023 x86_64 EBS 이미지와 8GiB 루트 요구량 검사를 통과했다. 매개변수는 Git 제외 runtime에만 보관하고 식별자/계정/ARN은 대화·문서에 출력하지 않았다.
- 승인 범위의 실제 배포 시도: 전체 예상 월 $7~10 승인을 유지하고 지정 CloudFormation 서비스 역할로 네트워크 CREATE 변경 세트를 만들었다. AWS ValidateTemplate 성공, 신규 Add 15개만 포함/기존 자원 변경 없음/EC2 t3.micro 1대/EIP 1개/모든 예약 DISABLED를 확인한 뒤 실행했다. 실제 리소스 생성 전 AWS의 가용영역 매개변수 조회에서 `ec2:DescribeAvailabilityZones`가 배포 역할 정책에 없어 자동 `ROLLBACK_COMPLETE`가 됐다. 전용 권한 파일의 누락이며 IAM 관리자 권한이나 실거래 잠금을 완화해서 우회하지 않았다.
- 생성·비용 상태 확인: 실패 스택의 StackResources 0개, EIP 0개, 종료되지 않은 EC2 0개를 실제 조회했다. 이 실패 시도로 NAT/EIP는 생성되지 않았다. 기존 VPC/Secret/ECR은 유지한다. CloudFormation raw 사건/식별자는 Git 제외 runtime에만 보관하며 CloudWatch를 내보내지 않았다.
- 변경 파일: `infra/paper-network-iam-bootstrap.yaml`에 서울의 `ec2:DescribeAvailabilityZones` 조회를 추가하고 작업 계정에 지정 네트워크 스택/변경 세트만 정리 가능한 `cloudformation:DeleteStack`을 추가했다. `tools/validate_paper_infrastructure.py`는 이 매개변수 조회 권한과 정리 ARN 범위를 검사한다. `infra/고정IP_모의배포_진행.md`는 기존 관리자 IAM 스택의 템플릿 교체/업데이트와 자원 없는 실패 네트워크 스택 정리 순서를 추가했다. `infra/paper-fixed-egress.yaml`은 EIP 연결 후 부팅 순서에 맞춰 패키지 재시도 주석만 바로잡았다. 이 공동 인수인계를 추가했다. 앱/매매 전략/이미지 내용 변경 없음.
- 검증: 수정본 2개의 실제 AWS ValidateTemplate 통과, 로컬 cfn-lint 1.57.2의 템플릿 3개 warning/error 0개 및 안전/IAM 크기·누락 권한 검사 통과, compileall·git diff --check 통과. Docker 포함 전체 unittest 재시도 `177개 통과`, skip 없음. 최초 검사에서는 기존 Docker Engine HTTP 500으로 컨테이너 검사 setUpClass가 실패해 175개 실행/error 1이었으며 해당 실패를 숨기지 않는다. 정상 Docker Desktop restart 성공 후 엔진/기존 검증 이미지 조회를 확인하고 전체 검사를 재실행해 통과했다. WSL 초기화/데이터 삭제/격리 약화 없음.
- 현재 미완료: 원격 IAM 정책은 사용자가 처음 등록한 버전이며 수정본은 아직 관리자 콘솔에 적용하지 않았다. 실패한 자원 없는 네트워크 스택은 ROLLBACK_COMPLETE로 남겼고, 정리 권한 적용 전 자동 삭제를 시도하지 않았다. NAT/고정 egress/SSM/OS 정지 타이머의 실제 검증, 키움 IP 등록, 앱 스택 배포 권한·수수료/세금·휴장일·Fargate/저장/알림 통합검증은 미완료다. 오늘/내일 자동 운용 가능을 확정하지 않는다.
- 다음 Codex: 사용자에게 관리자 CloudFormation의 **stock-automation-paper-network-iam** 기존 스택을 선택하고 업데이트/현재 템플릿 교체/최신 `paper-network-iam-bootstrap.yaml` 업로드를 한 단계씩 안내한다. UPDATE_COMPLETE 뒤 새 권한을 확인하고 StackResources 0개인 실패 네트워크 스택만 정리한다. 첫 실패의 runtime 기록·매개변수를 별도 보존한 다음 최신 조회/원격 검증/신규 변경 세트 검토 후 예약 DISABLED로 네트워크 재시도한다. 최초 부팅 검증 뒤 EC2 정지 확인, 실제 사설 Fargate egress 및 키움 모의 허용 IP/앱 통합검증을 이어간다. 동일 AWS 준비 작업의 기존 push 승인으로 수정 파일만 전달한다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지`, `LIVE TESTS: 전체 177개·CFN 로컬/원격 구문 통과 / 실제 통합 미검증`, `LIVE AWS DEPLOYMENT: 관리자 IAM 초기 등록 / 네트워크 최초 시도는 생성 전 롤백 / NAT·앱 미배포 / 예약 활성화 없음`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 22:49 KST — PC-C / 승인된 고정 egress 구성 준비·최신 이미지 ECR 반영

- 작업 PC alias: `PC-C`, 브랜치 `main`, 기준 `eada5b5`. 사용자가 월 `$7~10` 전체 예상 예산을 승인한 뒤 잠시 중단했고 `이어서 ㄱㄱ`로 재개했다. 예산 승인은 유지한다. AGENTS.md → PC-C 전체 인수인계 → 공동 인수인계를 읽고 실제 Git/코드 상태를 대조했다. 기존 미커밋 19:39 계획 기록은 PC-C 자체 작성분이라 보존했고 과거 기록을 수정하지 않았다.
- 변경 파일: `stock-automation/infra/paper-fixed-egress.yaml`, `paper-network-iam-bootstrap.yaml`, `requirements-validation.txt`, `고정IP_모의배포_진행.md`, 기존 `infra/cloudformation.yaml`, `tools/prepare_fixed_egress.py`, `tools/validate_paper_infrastructure.py`, `tests/test_fixed_egress_preparation.py`, `stock-automation/README.md`, `AWS_자동매매_실행가이드.md`, 이 공동 인수인계. 앱/전략 코드와 Dockerfile은 이번에 변경하지 않았다.
- 실제 네트워크 확인: 작업용 AWS CLI 로그인은 만료되어 사용자에게 재인증을 요청했고 완료 후 STS의 지정 IAM 사용자 여부를 확인했다(계정/ARN 미출력). 기존 VPC는 `10.77.0.0/16`, 공개 서브넷은 `10.77.0.0/20`, `10.77.16.0/20`이므로 이전 제안의 `10.77.16.0/24`는 겹친다. 첫 사용 가능한 `10.77.32.0/24`를 선택하고 /20과 /24 중첩·명시 경로/기본 경로·IGW 연결·DNS/AMI/프로필 검사를 구현했다. 공개 서브넷 실제 이름과 IAM 참조 태그 패턴도 대조했다. EIP 0개, 종료되지 않은 EC2 0개였다.
- 준비한 NAT 구성: 기존 VPC/공개 서브넷을 참조하며 사설 서브넷 1개, 전용 경로/SG/ENI, `t3.micro` 1대, EIP 1개다. EIP를 ENI에 연결한 뒤 인스턴스를 부팅한다. CPU credit standard, gp3 8GiB 암호화, IMDSv2 required, source/destination check 해제, SSH 없이 사설망 TCP 443만 전달한다. 패키지 설치 전에 systemd 정지 타이머를 등록하고 매 부팅 120분 후 stop한다. 정상 창은 평일 08:55~09:25·14:40~16:10, 토요일 07:50~08:40이고 시작/정지 예약 모두 기본 DISABLED다. 최초 생성 자체는 부팅하므로 검증 뒤 정지해야 한다. 22거래일·토요일 4회 가정 NAT 약 47.3시간/월이며 전체 예상 $7~10 범위 계획을 유지한다. 이 예상은 지출 상한이 아니다.
- 권한 구성: 관리자 콘솔용 IAM 전용 bootstrap은 NAT SSM 역할/프로필·태그 제한 시작/정지 역할·네트워크 전용 CloudFormation 배포 역할·작업 사용자 관리형 정책을 준비한다. 지정 스택/변경 세트 이름 및 service role에 한정하며 작업 사용자에 관리자 정책/IAM 편집/Secret 값 조회 권한을 추가하지 않는다. 관리형 정책을 사용해 기존 inline 총크기 문제를 피했다. 기존 VPC/공개 서브넷 참조, 신규 프로젝트 태그 자원 관리, t3.micro/암호화 gp3 8GiB/IMDSv2를 제한했다. 원격에서 실제 적용되는 권한인지는 배포 시 확인해야 한다.
- 기존 앱 템플릿 보완: 예약 11개의 네트워크를 `AssignPublicIp=DISABLED` 매개변수로 통일하고 허용값도 DISABLED만 둔다. cfn-lint가 발견한 잘못된 `AwsVpcConfiguration`을 공식 `AwsvpcConfiguration`으로 수정했다. 존재하지 않는 IAM action `dynamodb:TransactWriteItems` 대신 실제 원장 트랜잭션의 `PutItem/UpdateItem/GetItem/DeleteItem/ConditionCheckItem` 권한을 자체 PaperTable ARN에 제한해 제공했다. SNS/Telegram과 격리 설정·demo·LIVE_ORDER_ENABLED=0은 유지했다. Kakao Secret이 비어 있으면 빈 Resource 정책이 생기지 않도록 조건을 보완했다. 이는 역할 권한/배포 구조 보완이며 모의체결 로직·실주문 안전장치 변경이 아니다.
- 검증: 신규 네트워크 준비 검사 10개 포함 전체 unittest `177개 통과`(Docker opt-in 2개 포함, skip 없음), compileall 통과. 공식 배포 도구 `cfn-lint 1.57.2`를 Git 제외 runtime 도구 경로에 설치해 템플릿 3개의 서울 리전 스키마/IAM 검사 warning/error 0개, 오프라인 안전 구조·IAM 크기 검사 통과. 신규 CIDR 중첩·불완전/잘못된 경로·AMI 소유/아키텍처/디스크·잘못된 root 프로필·DNS 실패 시 중단을 검사했다. 정적 검사만으로 실제 NAT/Fargate/SSM 성공을 주장하지 않는다.
- ECR 실제 반영: 기존에 소스/이미지 프로그램 144개/임시 볼륨을 검증했던 로컬 권한 보완 이미지가 동일함을 확인하고 새 immutable 태그 `paper-tmp-20261014-4ae8632e82bc`로 업로드했다. Docker push exit 0, digest로 다시 내려받아 rootfs·linux/amd64·비루트 사용자와 소스/정적 파일 36개 및 CLI 일치 확인, ECR 표시 111005512 bytes. 비밀값은 메모리/stdin과 보호된 Docker Desktop 자격 증명 저장소만 사용했고 임시 설정 파일은 정리했다. 결과/URI는 Git 제외 `runtime/ecr-tmp-fix-upload-result.json`에 보관했다. 이미지 내용은 직전 offline Grype 결과와 같아 미해결 고유 69개/High 14개 판정을 유지하며 CVE 패치 완료나 외부 SBOM 검사를 주장하지 않는다.
- 실패/미완료: AWS CloudFormation ValidateTemplate은 AccessDenied, 공개 AL2023 SSM 매개변수는 AccessDeniedException이었다. 관리자 bootstrap 아직 미등록이며 새 EC2/EIP/프로그램 스택을 생성하지 않았다. 사용자에게 관리자 콘솔의 서울 CloudFormation을 열도록 요청했다. 실제 AMI/8GiB 요구량, bootstrap/OS 정지·재부팅/준비 상태, 사설 Fargate egress, 키움 허용 EIP, 앱 배포 IAM/수수료·세금/휴장일, API·S3/DynamoDB·알림 온라인 검증은 미완료다. 작업 지연·재시도/정지 창 초과 처리와 자동 실행 전 준비 확인도 실제로 검증·보완해야 한다. 내일 시작을 확정하지 않는다.
- 다음 Codex: 먼저 관리자 콘솔에서 `paper-network-iam-bootstrap.yaml`로 `stock-automation-paper-network-iam` 생성 안내를 한 단계씩 진행한다. 적용 후 작업 계정으로 조회 도구와 원격 템플릿 검증을 수행하고 예약 DISABLED 네트워크 배포, SSM/고정 egress 검증 뒤 EC2 정지를 확인한다. 이어 최신 ECR digest로 앱 스택/필수 데이터/온라인 모의 통합검증을 준비한다. 모두 성공한 다음 NAT/핵심 모의 예약 활성화를 판단하고 NXT/실거래는 유지 비활성이다. 이전 동일 AWS 준비 작업의 push 승인 범위에서 관련 파일만 전달하며 runtime·비밀값을 stage하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지`, `LIVE TESTS: PC-C 전체 177개 및 CFN 로컬 검증 통과 / 실제 통합 미검증`, `LIVE AWS DEPLOYMENT: 기존 ECR에 최신 검증 이미지 추가 / 프로그램·NAT 스택 미배포 / 예약 활성화 없음`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 19:39 KST — PC-C / AWS 시작 조건·고정 접속 IP 비용 구체화

- 작업 PC alias: `PC-C`, 기준 `main` / `eada5b5`. 사용자가 실제 AWS 모의투자를 언제 시작할 수 있는지 물었다. 현재 코드/이미지 검증과 Git 전달은 완료됐으나 프로그램 스택 미배포, 키움 허용 AWS 접속 IP 미확정, 실제 온라인 통합검증 미완료임을 설명했다. 내일 10월 15일 시작은 배포와 진단 통과를 전제로 하는 목표이며 확정 일정으로 약속하지 않았다.
- 제약 확인: 키움 공식 서비스 안내에서 허용 IP에서만 인증 가능/최대 10개 등록을 재확인했다. 현재 Fargate 개별 작업의 공인 IP를 새로 등록하는 방식은 예약형 자동 실행의 안정된 접속 IP를 보장하지 않는다. 기존 앱과 Fargate 안전 설정을 유지하면서 고정 egress를 마련하는 방향을 검토했다. https://openapi.kiwoom.com/intro/serviceInfo
- 구체화한 제안(미생성): 기존 VPC/공개 서브넷을 재사용하고 private subnet 1개, 소형 NAT 중계 EC2 `t3.micro` 1대, Elastic IP 1개를 준비한다. 애플리케이션·키움 키는 기존 Fargate/Secrets Manager에 유지하고 중계 호스트는 외부 HTTPS 전달만 담당한다. 중계 호스트는 예약 작업 시간에만 기동하고 완료 후 정지한다. 상시 단타 감시·항상 켜진 앱·NAT Gateway는 제안에 포함하지 않는다. private subnet과 Fargate AssignPublicIp DISABLED, source/destination check 해제·IP forwarding·진행 전 준비상태 검사·독립 정지 보호가 필요하다. 단일 호스트 장애 위험과 OS 유지보수 부담이 있다.
- 공식 가격 검증: 공개 AWS Price List 서울 리전 CSV에서 Linux OnDemand t3.micro `$0.013/시간`, gp3 `$0.0912/GB-월`, Fargate CPU `$0.04656/vCPU-시간`, 메모리 `$0.00511/GB-시간`을 확인했다. EIP는 사용/미사용 모두 `$0.005/시간`, 730시간 유지 시 `$3.65/월`이다. AWS 공개 요금 자료만 내려받았으며 계정 청구 데이터를 조회하지 않았다.
- 비용 계산 가정: 22거래일·작업 9회/일·5분/회, Fargate 0.5vCPU/1GB이면 월 16.5시간/약 `$0.47`. 중계 월 약 36.67시간이면 약 `$0.48`, gp3 8GB는 약 `$0.73`, EIP `$3.65`, 기존 Secret 3개 `$1.20`, ECR 약 `$0.02`, 로그/저장/요청/여유분을 합쳐 전체 월 `$7~10` 계획 범위다. 실제 AMI 디스크 요구량·기동/작업/튜닝 시간·장애 시 추가 실행·세금·환율·무료 크레딧·다른 계정 자원에 따라 달라진다. 비용 알림을 실제 지출 상한으로 설명하지 않는다.
- 비용·방식 확인 요청: 사용자의 기존 Secret/ECR 승인은 유지하되 중계 EC2와 EIP는 새 유료 자원이다. PC-C 전체 인수인계의 `사용자의 별도 승인 없는 유료 인프라 추가` 금지에 따라 전체 월 `$7~10` 예산/구성 방향 승인을 비동기 질문으로 요청했다. 이 기록 작성 시 답변은 대기 중이며 경과 시간을 승인으로 처리하지 않는다. 승인 없이 새 자원을 생성하지 않았다. 인프라 템플릿/배포 권한은 아직 준비 전이며 예산/방식 승인이 실제 검증 완료를 의미하지 않는다.
- 변경/검증: 이 인수인계와 Git 제외 `runtime/paper-fixed-egress-proposal.json`, 공개 가격 선택 자료만 작성. 제안 JSON과 공개 가격 필터/단가 대조 및 Git 제외 확인, `git diff --check` 통과. 앱/전략/안전 코드 변경 없어 전체 테스트 반복 없음(직전 Docker 포함 167개, 새 이미지 프로그램 144개 통과). AWS 자원 생성·설정 변경·예약·주문 없음.
- 다음 Codex: 예산/방식 답변을 반영하고 네트워크/예약 연동 템플릿과 해당 IAM 범위를 구체적으로 준비·테스트한다. 준비된 배포 내용을 승인 범위와 대조한 뒤 예약 비활성 상태로 배포, 새 고정 IP를 사용자에게 키움 모의 허용 목록에 등록하게 하고 실제 egress·키움/OpenDART·S3/DynamoDB/텔레그램 진단을 수행한다. 모두 성공한 다음 모의 예약 시작을 결정한다. 코드 테스트 통과만으로 실제 시작을 선언하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 호스트 167개·이미지 프로그램 144개 통과`, `LIVE AWS DEPLOYMENT: 기존 모의 준비 자원/ECR 유지 / 프로그램 스택 미배포 / 추가 유료 자원 미생성 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 19:27 KST — PC-C → PC-D / 임시 볼륨 권한 보완·실행 검증

- 작업 PC alias: `PC-C`, 브랜치 `main`, 작업 기준 `1ba698f`. 사용자가 앞선 `/tmp` 권한 발견 결과에 `ㄱㄱㄱ`로 보완 진행을 요청했다. 세 파일 인수인계와 실제 상태를 다시 대조하고 기존 19:14 검토 기록을 보존했다. 동일 AWS 준비 작업에 대한 앞선 commit/push 요청을 유지해 이번 수정 4개 파일만 Git 전달한다. runtime·키·토큰·원본 로그는 제외한다.
- 변경 파일: `stock-automation/Dockerfile`, `stock-automation/tests/test_container_tmp_runtime.py`, `stock-automation/README.md`, 이 공동 인수인계. 매매 로직·계좌·Secret·배포 템플릿의 비루트/read-only/capability drop/예약 비활성 설정은 변경하지 않았다.
- 보완 내용: 이미지의 `/tmp`를 UID/GID `65534:65534`, mode `0700`으로 초기화하고 `VOLUME ["/tmp"]`를 선언했다. 기존 ECS ContainerPath와 일치해 이미지 디렉터리 초기 정보를 볼륨에 복사할 수 있도록 했다. Python `TMPDIR=/tmp`도 명시했다. Fargate에 지원되지 않는 tmpfs 옵션을 템플릿에 넣거나 루트 사용자/파일시스템 쓰기를 활성화하는 방식으로 우회하지 않았다. 실제 Fargate 초기화 검증은 별도다.
- 새 회귀검사: `STOCK_AUTOMATION_TEST_IMAGE`를 지정했을 때만 로컬 Docker 통합검사 2개를 실행한다. 로컬 named pipe/unix 소켓을 확인하고 registry pull을 금지한다. 새 빈 named volume에 이미지 디렉터리가 초기화됐을 때 UID 65534의 임시 보고서 생성·내용 확인·정리, 기본 tempfile 경로, root 쓰기 차단, capability 0/no-new-privileges를 검사한다. `volume-nocopy`의 root/0755 기본 빈 볼륨은 PermissionError가 발생해야 통과하는 대조 검사다. 각 검사 컨테이너·볼륨을 정리한다. Docker가 없는 PC-D에서는 두 검사가 skip되므로 실제 이미지 검사 통과로 보고하지 않는다.
- 이미지 재빌드: 최신 base를 확인하고 cache 없이 linux/amd64 단일 이미지로 재빌드했다. base digest `70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f`, 새 이미지 manifest `4ae8632e82bccc6b74227507693754515d5e9128fda95e73eb9d43933cdd0910`. pip check 통과, boto3/botocore `1.43.113`, more-itertools `11.2.0` 설치. 새 이미지는 로컬 `stock-automation:dev`이며 기존 AWS ECR 이미지를 갱신하지 않았다.
- 검증 결과: 신규 Docker 통합 `2개 통과`, 이를 포함한 호스트 전체 unittest `167개 통과`(skip 없음), compileall 통과. 새 이미지와 초기화된 실제 named volume, network none/read-only/cap-drop ALL/no-new-privileges/init 조건에서 프로그램 테스트 `144개 통과`(Windows 설정 도구 21개 및 호스트 Docker 통합 2개는 호스트 전체 검사에서 확인). CLI help, 키움/boto3 import 및 소스/정적 파일 `36개` 해시 일치 통과. 검사 볼륨 정리, runtime Git 제외, 비밀정보 및 staged diff 검토와 `git diff --check` 통과.
- 취약점 재검사: 공개 DB built `2026-10-13T06:35:20Z`의 동일 Grype offline 설정으로 새 로컬 archive를 검사했다. 외부 연결 조회를 끄고 로컬 미사용 프록시로 차단했다. 결과 203개 package/CVE 매치/고유 94개이며 이전 검사와 패키지·버전·유형·CVE·심각도 매치가 모두 동일하다. 기존 Debian 패치 확인 25개, 미해결 69개/High 14개 판정을 유지한다. 임시 폴더 권한 수정은 CVE 패치가 아니며 ignore/VEX 예외를 추가하지 않았다.
- 실패·복구: 첫 빌드는 Docker Engine HTTP 500으로 실패했다. 정상 Docker Desktop restart 성공 후 builder/engine 상태를 확인했다. 서로 다른 context의 default builder를 지정한 명령은 context 불일치로 종료했고, `desktop-linux` 컨텍스트/동일 native builder를 명시한 재시도는 성공했다. WSL 초기화·등록 해제·데이터 삭제·강제 프로세스 제거 없이 복구했다. HTTP 500의 장기 재발 원인은 미확정이다.
- Git 전달/다음 작업: fetch 시점 원격 main과 HEAD는 0/0으로 일치했고 다른 PC의 새 변경이나 충돌은 없었다. push 결과와 커밋 ID는 최종 응답으로 보고한다. PC-D는 수신 후 세 인수인계 파일과 diff를 대조하고 일반 테스트 및 Docker opt-in 검사 여부를 구분한다. PC-C는 이 새 이미지의 ECR 반영, 키움 허용 IP·추가 비용 구조, 예약 DISABLED 배포 후 실제 Fargate 임시 파일·키움 demo 읽기·S3/DynamoDB/텔레그램 통합검증을 순서대로 진행한다. 유료 자원 추가는 구체화/비용 확인 후 승인 범위에 따른다.
- 미완료: 실제 Fargate 볼륨 초기화/온라인 진단/프로그램 스택 배포/모의 예약 활성화, 새 이미지 ECR 업로드, 미해결 취약점 공급자 업데이트. AWS 기존 준비 자원은 그대로이며 이번 작업으로 실제 모의 자동운용을 시작하지 않았다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지 / 실제 통합검증 미완료`, `LIVE TESTS: 호스트 전체 167개 및 새 이미지 프로그램 144개 통과 / Fargate·실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 기존 모의 자원/ECR 유지 / 권한 수정 이미지 로컬 검증 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 19:14 KST — PC-C / PC-D pull 수신 검토

- 작업 PC alias: `PC-C`, 브랜치 `main`, 수신 HEAD `1ba698f`(교재), 이전 PC-C 전달 `394330f`. 사용자 pull 완료 보고 후 AGENTS.md → PC-C 단독 인수인계 → 공동 인수인계를 읽고 실제 상태를 대조했다. 검토 시작 worktree clean, 충돌 없음. 이 응답에서 추가 pull/commit/push하지 않았다.
- 수신 내용: `456397d`의 컨테이너 격리 템플릿·보안 테스트·CVE 검토 문서·루트 README 현황·당일 NO_TRADE 기록과 `1ba698f`의 차트 교재를 확인했다. 합계 39개 파일 변경이며 GorapaduckPet 빌드 생성물 2개도 수신됐지만 주식/AWS 애플리케이션 변경은 아니다. 기존 파일을 되돌리거나 덮어쓰지 않았다.
- 코드·보안 검토: TaskDefinition의 비루트 `65534:65534`, read-only root, capability Drop ALL, init process, 전용 `/tmp`, `LIVE_ORDER_ENABLED=0`과 demo/memory 설정을 확인했다. 공식 PyPI PyYAML 6.0.3 wheel의 SHA256을 검증하고 runtime에만 풀어 CloudFormation YAML과 실제 TaskDefinition 구조·Core/NXT 기본 DISABLED를 검증했다. 시스템/프로젝트 의존성 파일은 변경하지 않았다. PC-D 문서는 미해결 고유 69개/High 14개를 유지하며 격리 완화와 패치 완료를 구분한다. 이번 검토에서는 최신 base 재빌드·Grype 재스캔을 수행하지 않았으므로 그 건수는 이전 검사 기록이다.
- 배포 전 발견 사항: 현재 Dockerfile에는 `/tmp`를 대상으로 하는 VOLUME 및 빈 ECS 볼륨의 소유권 초기화가 없다. AWS 공식 bind mount 안내는 기본 볼륨 root 소유/0755 및 Dockerfile VOLUME을 통한 초기 데이터/권한 설정을 설명한다(https://docs.aws.amazon.com/AmazonECS/latest/developerguide/bind-mounts.html). 동일 기본 상태를 로컬의 새 빈 volume-nocopy 볼륨으로 재현했을 때 UID 65534의 `/tmp` TemporaryDirectory 생성은 `PermissionError`; mode 1777 양성 대조에서는 성공했다. 실제 Fargate 결과는 아니지만 기본 권한에서의 실패를 확인했으며 AWS 배포 전 보완/실행 검증이 필요하다. 임시 파일은 aws_runtime.py의 종가 결정 보고서와 승격된 튜닝 결과 작성에도 사용된다. 문자열 기반 보안 테스트 4개 통과만으로 볼륨 쓰기 권한을 보장할 수 없다.
- 다음 보완 방향: 비루트·read-only·capability 제거는 유지하고 Dockerfile에서 ECS 전용 임시 디렉터리의 사용자/권한과 VOLUME 경로를 명시하는 등 초기화 방식을 마련한다. 대응 테스트는 root/0755 실패와 UID 65534 실제 쓰기를 확인하는 방식으로 구성한다. 이미지 재빌드/재스캔 및 예약 DISABLED Fargate 검증 전에 이 항목을 먼저 처리한다. 이번 사용자 요청은 수신 확인이므로 Dockerfile/배포 템플릿/테스트를 임의 수정하지 않았다.
- 작성 문서 확인:
  - 교재 통합본과 00~23 장별 24개 본문을 제목 수준과 내비게이션을 제외하고 대조해 일치 확인. Markdown 28개의 UTF-8·코드 블록·로컬 문서 링크 정상. ZIP CRC 정상, 27개 파일의 본문 일치 확인(현재 Git checkout의 CRLF 때문에 원본 ZIP과 바이트는 다르지만 줄바꿈 외 차이 없음). 교재의 수급 가점 설명은 실제 종가 코드 +1.5/+1.5, 단타 +3/+3과 일치한다.
  - Notion 공식 가져오기 안내의 ZIP/Markdown/데스크톱·웹 지원을 대조했다. 실제 Notion 업로드/모바일 배치는 수행하지 않았다. https://www.notion.com/help/import-data-into-notion
  - 15:10 분석 보고서·실시간 모의 현재본·추천 이벤트의 NO_TRADE/신규 체결 없음 기록을 확인했다. CSV 28열과 ID 단일성 정상. 이는 파일 기록 검토이며 현재 시세를 다시 검증하거나 새로운 추천/체결을 생성한 것은 아니다.
  - 15:40 인수인계에는 교재가 외부 D:/Dev 문서 폴더에 있어 Git 대상이 아니라고 적혀 있지만 이후 실제 `1ba698f` 커밋에서 저장소 루트 `사부의_차트교재_2026-10-14/`에 29개 파일이 추가됐다. 현재 PC-C에서도 모두 존재하므로 별도 복사 없이 읽을 수 있다. 과거 기록은 유지하고 이 기록으로 현재 상태를 정정한다.
- 검증 결과: 새 보안 집중 테스트 `4개 통과`, 전체 unittest `165개 통과`, compileall 통과. CloudFormation 구문/안전 구조, 교재 본문/링크/ZIP, 이벤트 CSV 검사와 수신 diff `git diff --check` 통과. Docker Desktop이 꺼져 있어 정상 시작 후 로컬 임시 폴더 검사만 수행했다. 검사 컨테이너와 신규 전용 볼륨은 정리했다. AWS 자원 생성·배포·예약·Secret 읽기/변경은 수행하지 않았다.
- 변경 파일: 이 공동 인수인계만 추가, Git 제외 runtime에 YAML 파서와 `/tmp` 검사 결과 보관. 다음 PC-D/PC-C는 위 임시 폴더 권한 문제를 먼저 보완한 뒤 키움 허용 IP·비용·온라인 API·저장소·알림 통합검증을 진행한다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지 / 실제 통합검증 미완료`, `LIVE TESTS: PC-C 전체 165개 통과 / 실제 Fargate·체결 미검증`, `LIVE AWS DEPLOYMENT: 기존 모의 준비 자원/ECR 유지 / 강화 템플릿 수신 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 15:40 KST — PC-D / Notion 학습용 차트 교재 초판

- 요청·완료: 사용자가 기초부터 책처럼 읽을 차트 교재를 요청했고, Notion에 직접 가져올 수 있도록 Markdown으로 작성해 달라고 확정했다. 기본 문서 저장 규칙에 따라 `D:/Dev/2026/SKR/docs/사부의_차트교재_2026-10-14/`에 완성본을 저장했다. 기존 Sabu 문서와 프로그램 코드는 변경하지 않았다.
- 결과물: `사부의_차트_교재_통합본.md` 약 38,584자, `장별/`의 00~23 본문 24개, `교재_목차.md`, `휴대전화_매매전_체크리스트.md`, `Notion_가져오기_안내.md`, `Notion_장별_가져오기.zip`. Markdown 28개와 ZIP 1개 총 29개 파일이다. ZIP은 통합본 중복을 제외한 Markdown 27개, 52,246 bytes다.
- 내용: 호가·캔들·추세·이평·거래량·시장 폭·수급·보조지표·뉴스, 매수 패턴·확인 손절과 비상선·10만원 수량 계산·주문 상태·종가배팅·전략 분리·현재 코드의 수급 가점, 가상 사례 8개와 문제·해설·통계·심리·30일 훈련·노트·용어를 포함했다. AI의 검증된 실전 성과나 수익 보장을 주장하지 않고 정의·가설·운영 규칙을 구분했다. 모든 종목·체결 사례는 가상이며 실제 추천·모의 매매 원장에 추가하지 않았다.
- 검증: UTF-8, 코드 블록·제목 구조, 24장 순서와 본문 분할 일치, 로컬 문서 링크, 예제 수량·VWAP·거래대금·기대값·부분익절·손익과 R 계산, ZIP CRC와 27개 파일 바이트 일치 검사 통과. 최종 저장된 29개 파일은 제작본과 바이트 일치를 확인했다. 프로그램 변경이 없어 전체 테스트 반복 없음(직전 PC-D 165개 통과 유지).
- 저장·전달 주의: 교재는 사용자 지정 기본 문서 폴더에 있어 `D:/Test` 저장소 Git 대상이 아니다. PC-C에서 원문 파일도 필요하면 별도로 복사하거나 사용자가 Notion에 가져온 교재를 사용한다. Notion의 실제 가져오기·모바일 배치는 사용자 확인 대상이며 내부 파일 링크가 페이지 링크로 변환되지 않으면 Notion에서 다시 연결한다. 페이지·공유 설정 변경은 수행하지 않았다.
- 변경 파일: 이 공동 인수인계와 위 외부 문서 폴더의 새 교재 파일. 기존 기록·다른 미커밋 변경 보존, commit/push 없음. 다음 Codex는 학습 질문 시 해당 장의 가상 예제와 실제 종목 판단을 구분하고, 코드 설명은 최신 버전과 대조한다.
- 실거래 상태: 코드·AWS·Secret·스케줄 변경 없음, 실주문 없음, 실거래 비활성 유지, 비상정지 해제 없음. 프로그램 실행·통합검증의 다음 담당은 기존 PC-C 계획대로다.

### 2026-10-14 15:12 KST — PC-D / 당일 실시간 추천 검토·NO_TRADE

- 요청·결과: 오늘의 추천을 현재 단기 매매 판단으로 검토했다. 기존 실시간 AI 모의 포지션은 없고 양 시장 상승 목록을 새로 스캔했다. 지수 기준 15:09:55 KST 코스피 -0.48%·코스닥 -1.93%, 후보 기준 15:09:56 KST다. 라온시큐어의 당일 AI 확인서 보도·분봉 회복은 관찰했으나 NXT 비대상·종목 수급 미확인, LS머트리얼즈·빛샘전자 분봉 20이평 미회복 등으로 최종 `NO_TRADE`. 신규 0주·투자금 0원·모의 현금 601,400원 100% 유지.
- 변경 파일: `docs/실시간 데이터 확인/2026-10-14_1510_korean-stock-analysis.md`, 같은 폴더의 `실시간_모의투자_현재본.md`, `docs/프로그램 설계/추천_이벤트_현재본.csv`, 이 공동 인수인계. 종가배팅 요청이 아니므로 해당 Excel·일일기록은 변경하지 않았다. 기존 개발 변경을 보존했고 commit/push하지 않았다.
- 검증: 새 CSV 이벤트 ID 단일성·28열·0주·체결가 공란 검증과 변경 문서 공백 검사 통과. 프로그램 변경이 없어 전체 테스트 반복 없음(직전 PC-D 전체 165개 통과). 실제 주문·사용자 체결을 추정하지 않았다.
- 미확인·위험: NXT 사이트 접근 제한, 개별주 당일 기관·프로그램·호가와 일봉 검증 미완료. 기사 검색 결과는 확인했으나 본문 직접 조회 실패를 보고서에 명시했다. 시세는 네이버의 실시간 표시 API를 단발 조회했으며 이후를 감시하지 않는다.
- 다음 Codex: 시장 질문 시 열린 모의 포지션부터 다시 확인하고 최신 시세로 새로 판단한다. 프로그램 작업은 기존 PC-C 재빌드·보안 재검사·AWS 모의 통합검증을 이어간다. 실거래 비활성·실주문 없음·비상정지 해제 없음.

### 2026-10-14 15:06 KST — PC-D → PC-C / GitHub 진행 현황 갱신

- 작업 PC alias: `PC-D`, 경로 `D:/Test`, 브랜치 `main`, 기준 커밋 `394330f`. 사용자 재개 요청에 따라 이전 1·2단계 이후 남겨 둔 루트 README 현황 갱신을 진행했다. AGENTS.md → PC-C 전체 인수인계 → 공동 인수인계와 실제 diff를 대조했다. 새 pull·commit·push는 없으며 기존 미커밋 작업과 생성물을 보존했다.
- 변경 파일: `README.md`, 이 공동 인수인계. 매매 코드·컨테이너 설정·실거래 제어는 이번 세션에서 변경하지 않았다.
- 완료한 작업: GitHub 테스트 배지·진행도 그래프·완료 기준을 140개에서 PC-D 재검증 165개로 갱신했다. PC-C의 모의 Secret·네트워크·ECR 준비는 기존 실행 기록에 근거해 표시하고, 프로그램 스택 미배포·예약 비활성·Fargate 격리 설정 미검증을 구분했다. 미해결 CVE 69개/High 14개는 2026-10-14 기존 검토 자료의 수치로 남기고 보안 검토 링크를 연결했다. 2/5 관문은 개발 진행 상태이며 실거래 안전성의 백분율이 아님을 명시했다.
- 테스트·수동 검증: 전체 unittest `165개 통과`, Python `compileall` 통과, README 로컬 링크 10개 존재 확인, 의도한 변경의 `git diff --check` 통과. 문서 변경이므로 새 단위 테스트는 추가하지 않았다. 최초 테스트 명령은 PYTHONPATH 누락 및 로컬 truststore 부재로 실패했으며, src 경로와 PyPI SHA-256 검증된 truststore 0.10.5 wheel을 `/tmp`에서만 로드해 재실행했다. 시스템 Python·저장소 의존성 파일을 변경하지 않았다.
- 실패·미확인·남은 위험: 이번 세션은 AWS 상태를 온라인 조회하지 않았고 Docker 재빌드·Grype 재스캔·Fargate 실행·키움 모의 연결을 수행하지 않았다. README의 배포 상태는 PC-C 기존 기록 기준이다. 취약점은 새 패치·새 이미지로 재판정한 것이 아니며 미해결 상태를 유지한다. PC-C 전체 인수인계 본문의 140개 표기는 과거 기준이므로 현재 회귀검증 수는 이 최신 기록의 165개를 따른다.
- 다음 Codex의 첫 작업: PC-C에서 사용자 commit/push 이후 pull하고 세 인수인계 파일과 diff를 확인한다. 전체 165개 테스트 재현 → 최신 이미지 재빌드·동일 방식 재스캔 → 키움 허용 IP 구조·추가 비용 확정 → 예약 DISABLED 배포·Fargate 모의 smoke test 순으로 진행한다. 기존 AWS 준비 자원을 중복 생성하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 기존 강화 유지 / 실제 통합검증 미완료`, `LIVE TESTS: PC-D 전체 165개 통과 / 실제 체결·Fargate 미검증`, `LIVE AWS DEPLOYMENT: 기존 인수인계 기준 모의 ECR 이미지 준비 / 프로그램 스택 미배포 / 이번 AWS 변경 없음`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미조회 / 해제하지 않음`.

### 2026-10-14 08:21 KST — PC-D → PC-C / Docker 취약점 검토·격리 강화

- 작업 PC alias: `PC-D`, 브랜치 `main`, 기준 커밋 `394330f`. pull 후 `AGENTS.md` → `PC-C_단독진행_전체인수인계.md` → 이 문서를 다시 읽고 실제 Git 상태·코드·테스트와 대조했다. 사용자는 제안 작업 중 1번 취약점 검토·보완과 2번 전체 검증까지만 요청했으므로 GitHub 루트 README 진행도 수정은 하지 않았다. commit/push도 수행하지 않았다.
- 변경 파일: `stock-automation/infra/cloudformation.yaml`, `stock-automation/tests/test_container_security.py`, `docs/운영 검증/2026-10-14_Docker_취약점_PC-D_검토.md`, 이 공동 인수인계. 기존 CRLF 차이와 GorapaduckPet 생성물 변경은 건드리지 않았고 이번 작업에 포함하지 않는다.
- 취약점 검토: CSV 203개 package/CVE 행을 고유 CVE로 다시 집계해 미해결 69개(High 14, Medium 25, Low 5, Negligible 25)를 확인했다. High 14개를 Debian 공식 Security Tracker의 2026-10-14 상태와 코드 호출 경로에 대조했다. 모두 trixie 설치 가능 수정 버전이 없어 `FIXED`나 오탐으로 닫지 않았다. ncurses CLI, mount/nsenter, ACL, Perl POD/tar, glibc 특정 함수와 C/C++ 특정 입력 경로는 현재 프로그램에서 호출되지 않지만 이는 노출 제한일 뿐 패치가 아니다. zlib 항목을 포함한 High 14개는 업데이트·재스캔 대상이며 실거래 배포 차단 사유로 유지한다.
- 격리 강화: ECS Task Definition에 `65534:65534` 비루트 사용자, read-only root filesystem, Linux capability 전체 제거, init process를 명시했다. Python 임시 작업을 위해 빈 `runtime-tmp` 볼륨만 `/tmp`에 쓰기 가능하게 마운트했다. `KIWOOM_MODE=demo`, 메모리 토큰 저장과 함께 `LIVE_ORDER_ENABLED=0`을 명시했다. 실계좌 Secret·주문 권한·실거래 스케줄은 추가하지 않았다.
- 테스트: 새 컨테이너 보안 회귀 테스트 4개를 추가했다. 최초 전체 실행은 PC-D에 `truststore`가 없어 기존 텔레그램 테스트 4개만 환경 의존성으로 실패했다. 저장소·시스템 Python을 바꾸지 않고 PyPI 공식 wheel의 SHA-256을 확인해 `/tmp`에서만 로드한 뒤 전체 unittest `165개 통과`. `compileall` 통과, CloudFormation YAML 구문 로드 통과, IAM JSON 3개 파싱 통과, CSV 203행/미해결 고유 69/High 14 검증 통과, 의도한 변경의 `git diff --check` 통과.
- 실패·미확인: PC-D에는 Docker가 없어 변경 후 이미지 빌드·재스캔과 ECS Fargate smoke test를 실행하지 못했다. read-only root에서 `/tmp` 임시 작업, 키움 demo 읽기, S3·DynamoDB 쓰기가 실제 Fargate에서 정상인지 PC-C 확인이 필요하다. 새 기반 이미지에서도 High 14개가 남는지 재검사해야 한다.
- 다음 Codex의 첫 작업: PC-C에서 세 파일 인수인계와 실제 diff를 다시 확인하고 전체 165개 테스트를 재현한다. 변경 세트로 Task Definition의 비루트/read-only/capability drop/전용 `/tmp`를 확인하되 모든 스케줄을 `DISABLED`로 유지한다. 모의 smoke test와 최신 base image 재빌드·동일 Grype 방식 재스캔 결과를 새 기록으로 남긴다. 취약점 ignore/VEX로 숫자만 0으로 만들지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 강화했으나 실제 통합검증 미완료`, `LIVE TESTS: PC-D 전체 165개 통과 / Docker·Fargate 미검증`, `LIVE AWS DEPLOYMENT: 기존 ECR 모의 이미지 유지 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 해제하지 않음`.

### 2026-10-14 01:02 KST — PC-C → PC-D / 사용자 승인 Git 전달

- 작업 PC alias: `PC-C`, 브랜치 `main`, 작업 기준 `bb5946e`. 사용자가 `push까지 해줘`로 이번 PC-C 준비 작업의 commit/push를 명시적으로 승인했다. 세 파일 인수인계와 실제 상태를 확인했으며 이번 작업에 속한 13개 파일만 전달 대상으로 선정했다. runtime·자격 증명·도구 바이너리·원본 로그를 포함하지 않는다.
- 원격 비교: `git fetch origin` 성공, 검사 시점 `HEAD...origin/main`은 0/0이었다. pull이나 merge 없이 기존 PC-C 변경을 유지했다. push는 아래 검사 후 일반 방식으로 수행하며 force push를 사용하지 않는다. 성공 여부와 최종 커밋 ID는 사용자 응답에서 보고하고 PC-D가 수신 후 git log로 대조한다.
- 전달 파일 13개:
  - `Codex_세션간_공동_인수인계.md`
  - `stock-automation/Dockerfile`, `stock-automation/README.md`
  - `docs/운영 검증/2026-10-14_Docker_취약점_검증.csv`
  - `stock-automation/infra/paper-secret-setup-policy.json`, `paper-network-inspect-policy.json`, `paper-ecr-upload-policy.json`
  - `stock-automation/tools/setup_telegram.py`, `upload_paper_secrets.py`, `requirements.txt`, `grype-offline.yaml`
  - `stock-automation/tests/test_telegram_setup.py`, `test_paper_secret_upload.py`
- 변경 목적: 사용자 직접 입력과 Windows 자격 증명 저장소를 사용하는 로컬 텔레그램/모의 Secret 설정 도구, 해당 준비 권한의 범위 제한 정책, Debian/Python 보안 업데이트를 적용한 Docker 빌드, 외부 메타데이터 전송 없는 검사 설정과 CVE 대조 자료를 함께 전달한다. 모의 Secret·ECR 이미지는 앞선 승인으로 이미 AWS에 준비돼 있으므로 PC-D에서 설정 도구를 재실행하거나 자원을 중복 생성하지 않는다.
- push 전 검증: 설정 도구 집중 테스트 12개/9개 통과, 전체 unittest `161개 통과`, compileall 통과. JSON 3개 구문·허용 작업·서울 리전 범위 검사 통과. CSV 203행/고유 94개/Critical 2개 공식 수정판 판정 로드 검증 통과. Grype offline YAML을 사용하는 로컬 archive 재검사 통과(외부 연결 조회 비활성, 로컬 미사용 프록시). 전달 파일 비밀정보 패턴 검사, staged diff 검토, `git diff --check` 통과. 직전 이미지 프로그램 테스트 140개와 ECR push 종료 코드 0/digest 다운로드/36개 파일/CLI 검증도 유지한다.
- PC-D 수신 절차: D:/Test에서 기존 작업을 보존하고 dirty/충돌 여부를 먼저 확인한다. 정상 상태에서 main을 pull한 뒤 AGENTS.md → PC-C 단독 인수인계 → 이 공동 인수인계를 다시 읽고 전체 테스트를 실행한다. 이제 Git 전달을 사용하므로 앞선 00:58 기록의 zip은 선택적인 과거 스냅샷이다. 최신 파일은 이번 전달 커밋을 기준으로 한다.
- 담당/다음 작업: PC-D는 남은 고위험 14개 및 기타 55개 CVE의 실제 영향과 수정·조건부 위험을 검토하고 관련 테스트/전체 테스트/근거를 반환한다. PC-C는 AWS 고정 접속 IP·짧은 모의 예약 실행 구조와 비용을 준비하고, 수정 수신 후 재빌드·재검증한다. 새 유료 자원은 기존 승인 범위를 넘으면 먼저 비용과 구체적인 변경을 확인받는다.
- 미완료·남은 위험: 취약점 69개는 해결 완료가 아니다. 키움 AWS 허용 IP, 온라인 키움/OpenDART·텔레그램·데이터 저장 통합검증, 프로그램 스택/모의 예약 실행이 미완료다. Docker HTTP 500은 이전 정상 재시작 후 작업됐으나 장기 재발 원인은 미확정이다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 이미지 프로그램 140개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의 준비 자원과 검증 이미지 ECR 저장 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`. 실거래 환경변수 활성화나 안전장치 해제 없이 전달한다.

### 2026-10-14 00:58 KST — PC-C → PC-D 취약점 검토 담당 지정

- 작업 PC alias: `PC-C`, 기준 `main` / `bb5946e`. 사용자가 다음 단계 중 `1. 남은 취약점 검토`를 PC-D에게 맡기겠다고 명시했다. PC-D에 메시지를 직접 전송하거나 별도 에이전트를 실행하지 않았으며 사용자가 자료를 전달한다.
- 담당 구분: PC-D는 취약점의 실제 영향·공식 수정판·필요한 코드/의존성/이미지 수정과 테스트를 담당한다. PC-C는 AWS 접속 IP/실행 구조/비용 구체화, 모의환경 배포 및 통합검증을 담당한다. PC-D 검토 결과 없이 모의 운영 준비가 완료됐다고 판단하지 않는다.
- PC-D 검토 자료:
  - `docs/운영 검증/2026-10-14_Docker_취약점_검증.csv`: 원본 203개 package/CVE 매치, 고유 94개. Debian 수정판 대조 25개(치명적 raw 2개 포함), 미완료 69개 중 High 14개.
  - `stock-automation/Dockerfile`, `stock-automation/README.md`, `stock-automation/tools/grype-offline.yaml`: PC-C에서 적용/검증한 보안 업데이트와 외부 메타데이터 전송 없는 검사 설정.
  - AGENTS.md, PC-C 단독 인수인계, 이 공동 인수인계의 최신 기록. 이 7개 파일만 Git 제외 `runtime/PC-C_to_PC-D_2026-10-14_0058.zip`에 묶어 전달 준비한다. archive에 runtime 원본·레지스트리 URI·키·토큰·자격 증명·공개 DB/도구 바이너리를 넣지 않는다.
- PC-D 첫 작업: 전달 자료는 별도 임시 폴더에서 기존 D:/Test 상태와 비교한다. Git pull이 가능해도 먼저 미커밋/충돌 상태를 확인하며 파일을 통째로 덮어쓰지 않는다. CSV에서 남은 고위험 14개를 우선 검토하고 나머지 55개도 추적한다. 공식 수정 여부/현재 코드 호출 경로/조건부 위험/불명 항목을 구분한다. 수정된 OpenSSL backport를 단순 upstream 버전 비교로 다시 취약하다고 판단하지 않는다. runtime/의존성까지의 호출 경로를 확인하지 않고 미사용으로 단정하지 않는다.
- 유지할 사용자 제한: Scout/SBOM/이미지 패키지 메타데이터 외부 전송 금지. 공개 취약점 DB를 별도로 내려받아 로컬 분석한다. 검사 예외나 안전장치 제거로 결과를 통과시키지 않는다. 실계좌 Secret·실주문·비상정지 해제·실거래/상시 단타 예약 활성화 금지.
- PC-D 반환 결과: 파일별 수정 diff, 관련 검증 및 전체 테스트 결과, CVE별 근거/처리/잔여 위험, 모의 배포에 필요한 제한을 새 인수인계 기록에 추가한다. Git commit/push는 사용자 승인 범위에 따른다. PC-C는 수정본 수신 후 세 파일 리뷰·재빌드·동일 방식 취약점/실행 검증·필요한 새 ECR 업로드를 수행한다.
- 변경/검증: 이 공동 인수인계와 Git 제외 전달 zip만 추가. 프로그램 코드 변경 없음. 직전 호스트 전체 161개·이미지 프로그램 140개 통과와 AWS push/digest 다운로드/36개 파일 검증 통과 기록 유지. 전달 목록 검사와 `git diff --check` 통과. 현재 PC-C 변경은 미커밋·미push 상태이므로 PC-D에서 pull만 해서는 최신 로컬 자료를 받지 못한다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 호스트 161개 및 이미지 프로그램 140개 통과`, `LIVE AWS DEPLOYMENT: 검증 이미지 ECR 저장 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.

### 2026-10-14 00:56 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 기준 `main` / `bb5946e`. 세 파일 인수인계와 실제 Git 상태·Dockerfile·직전 검증 결과를 대조했다. 기존 미커밋 변경을 보존했다. pull/commit/push 없음.
- 사용자 요청/승인: 사용자가 다시 시도를 요청한 후 범위를 `AWS 이미지 업로드 재시도`로 구체적으로 선택했다. 이 승인을 근거로 기존 저장소에 새 보안 업데이트 이미지를 별도 태그로 업로드했다. 새 서버/네트워크 자원 생성·예약 활성화·실주문은 이 요청에 포함하지 않았다.
- 업로드 결과:
  - 지정 IAM `stock-paper-operator`와 서울 리전 STS 확인. 기존 ECR 저장소 `stock-automation`의 `IMMUTABLE` 설정을 유지했다. 검증한 로컬 이미지 ID와 현재 이미지 ID 일치를 재확인했다.
  - 새 태그 `paper-security-20261014-ef070ce8caa5`로 push했다. 이번 Docker push 종료 코드는 `0`이며 이전 manifest PUT HTTP 400 오류가 이번 업로드에서는 발생하지 않았다. 이전 오류의 정확한 원인이 확정됐다는 뜻은 아니다.
  - 저장된 새 이미지 digest로 다시 다운로드했다. 원본/다운로드 이미지의 RootFS 레이어 일치, linux/amd64, 비관리자 사용자 `65534:65534`, 소스/정적 파일 36개 해시 일치, 키움/boto3 import 및 CLI help 검증 통과.
  - 새 이미지 ECR 저장 크기 `110,988,464 bytes` 확인. 기존 이미지를 덮어쓰거나 삭제하지 않았다. 이미지 보관량 증가가 있으며 서버 실행 비용은 발생시키지 않았다.
  - ECR 인증값은 메모리와 password-stdin으로 전달하고 Docker Desktop native credential helper를 사용했다. 프로젝트 config에 평문 auth가 없음을 확인하고 임시 인증 config 디렉터리를 정리했다. 원문 계정 ID·레지스트리 URI·키·토큰을 일반 출력/공유 파일에 기록하지 않았다. Scout나 다른 외부 서비스로 SBOM을 전송하지 않았다.
- 변경 파일: 이 공동 인수인계, Git 제외 `runtime/ecr-security-upload-plan.json`, `runtime/ecr-security-upload-result.json`, `runtime/retry_ecr_security_upload.py`. Dockerfile/README/보안 검사 설정/검증 CSV는 직전 세션의 변경을 보존했다. 매매 로직·실거래 설정 변경 없음.
- 검증 결과: 이번 AWS push 및 digest 다운로드/레이어/36개 파일/CLI 검증 통과. 직전 동일 소스와 이미지의 호스트 전체 `161개`, 이미지 프로그램 `140개` 테스트 통과 기록 유지. 코드 변경 없어 전체 테스트 반복 없음. runtime Git 제외와 `git diff --check` 통과.
- 보안 검토 상태: 이미지 업로드는 파일 저장/검증 완료이며 운영 보안 승인 완료를 의미하지 않는다. 직전 검토의 미완료 고유 CVE 69개 중 High 14개를 유지한다. CVE 예외 추가·비상정지 해제·실거래 활성화 없음.
- 다음 Codex의 첫 작업: 배포 준비에는 최신 `runtime/ecr-security-upload-result.json`의 검증된 digest URI를 사용한다. 이전 `runtime/ecr-upload-result.json`은 과거 이미지 검증 정보다. 남은 취약점의 실제 영향과 AWS 제한 설정을 검토하고, 키움 허용 IP를 만족하는 짧은 예약 실행 구조/비용을 구체화한 뒤 필요한 추가 승인만 받는다. AWS 프로그램 스택·온라인 API 진단은 계속 미완료다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 호스트 161개 및 이미지 프로그램 140개 통과 / 이번 업로드 이미지 재검증 통과`, `LIVE AWS DEPLOYMENT: 새 검증 이미지 ECR 저장 완료 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.

### 2026-10-14 00:52 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 기준 `main` / `bb5946e`. 사용자 요청은 삭제 후 최신 보안 업데이트를 반영한 Docker 재빌드와 외부 메타데이터 전송 없는 취약점·실행 검증이다. 세 파일 인수인계와 실제 상태를 대조하고 기존 미커밋 작업을 보존했다. pull/commit/push 없음.
- 완료한 변경:
  - `stock-automation/Dockerfile`: Python 3.13의 Debian trixie 이미지를 명시하고 빌드 시 Debian 업데이트, pip/런타임 패키지 업데이트와 `pip check`를 적용했다. 기본 실행 사용자 `65534:65534`와 기존 실거래 안전장치를 유지했다.
  - `--pull --no-cache --platform linux/amd64 --provenance=false --sbom=false`로 새 이미지 `stock-automation:dev` 빌드 성공. 확인한 base digest는 `70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f`, 새 manifest digest는 `ef070ce8caa5fd9f2516b105654cdab4869c6aeade5469ef9a5fe6d3eb43b8dd`이다. 이전 태그를 덮어쓰는 AWS push는 하지 않았다.
  - Debian `liblzma5`를 `5.8.1-1+deb13u2`로 갱신했다. 런타임 boto3/botocore는 `1.43.112`, urllib3는 `2.8.0`이다. 그 밖의 설치 버전은 Git 제외 검사 원본에서 확인한다.
  - `stock-automation/tools/grype-offline.yaml`과 README 실행법 추가. 공개 DB 다운로드를 검사와 분리하고 검사 중 DB 자동 갱신·앱 업데이트·외부 추가 조회를 끈다. DB 해시와 최대 5일 유효기간 검사는 유지했다.
- 외부 전송 없는 검사:
  - 앞서 checksum을 확인한 공식 Grype `v0.120.1`로 공개 취약점 DB를 준비했다. DB schema `v6.1.10`, built `2026-10-13T06:35:20Z`, 상태 valid 확인.
  - 로컬 Docker archive를 입력으로 분석했다. 검사 중 HTTP/HTTPS 프록시를 로컬 미사용 포트로 지정하고 자동 업데이트와 외부 추가 조회를 껐다. Scout 호출·이미지/SBOM/패키지 목록 외부 업로드를 하지 않았다. 공개 Grype/Debian DB와 보안 공지 다운로드만 수행했다.
  - 원본 Grype 결과는 `203개 package/CVE 매치`, 고유 CVE `94개`: raw Critical 2 / High 73 / Medium 60 / Low 16 / Negligible 52. 같은 취약점이 여러 패키지에 중복 검출된다. 기존 Scout 화면의 35건과 스캐너·DB·집계 범위가 달라 수치 증감으로 해결 여부를 판단하지 않는다.
  - Debian 공개 보안 DB, 이미지 내부 `dpkg-query` 소스/패치 버전 및 `dpkg --compare-versions`로 대조했다. 고유 CVE 25개는 설치 버전에서 Debian 수정판이 반영된 것으로 확인됐다. 여기에는 raw Critical 2개(CVE-2026-63073, CVE-2026-75803)가 포함된다. 실제 OpenSSL은 `3.5.7-1~deb13u3`이며 단순 upstream 3.5.7 비교가 Debian backport를 놓친 사례다. 공식 근거: https://security-tracker.debian.org/tracker/CVE-2026-63073 , https://security-tracker.debian.org/tracker/CVE-2026-75803 . gzip 항목도 Debian 패치 버전을 대조했다.
  - 나머지 고유 CVE `69개`는 해결 완료로 처리하지 않았다(추가 검토 High 14 / Medium 25 / Low 5 / Negligible 25). Python 런타임/바이너리·Debian 미수정·공급자가 minor issue로 분류한 항목을 포함한다. 고위험 14개는 Perl 2, ncurses 1, glibc 2, gcc/libstdc++ 2, util-linux 4, acl 2, zlib 1에 걸쳐 있다. 로컬 권한·특정 함수 호출 조건이 있는 항목도 있으나 의존성 전체 호출 경로와 AWS 실행 설정을 아직 검증하지 않았으므로 영향을 일괄 배제하지 않는다. zlib CVE-2026-85091은 Debian tracker가 open이며 영향 버전 범위에 논의가 있어 미확인으로 유지한다.
  - 현재 DB에서 PyPI 패키지 취약점 매치는 0개였지만 전체 코드 보안 감사 완료 또는 전체 취약점 0개를 뜻하지 않는다. 스캐너 ignore/VEX 예외를 추가해 결과를 숨기지 않았다.
- 검증 결과: 호스트 전체 unittest `161개 통과`, compileall 통과. 새 이미지의 실제 런타임 의존성으로 프로그램 테스트 `140개 통과`(로컬 사용자 설정 도구 테스트 21개는 호스트 전체 검사에 포함). 네트워크 차단·읽기 전용·cap-drop ALL·no-new-privileges 컨테이너에서 소스/정적 파일 `36개` 해시 일치, CLI help와 키움/boto3 import 통과. pip check, offline 설정을 사용한 실제 재검사, CSV 203행 로드/치명적 항목의 공식 수정판 대조, runtime Git 제외 및 `git diff --check` 통과.
- 전달 파일: Dockerfile, README, `tools/grype-offline.yaml`, `docs/운영 검증/2026-10-14_Docker_취약점_검증.csv`(원본 203매치의 패키지/버전/CVE/공급자 상태/판정/출처), 이 공동 인수인계. Git 제외 runtime에 이미지 archive, 공개 DB, 설치 버전, 스캐너 원본, 검사 요약과 테스트 출력 보관. 비밀값·계정 번호·ECR URI는 전달 CSV/문서에 포함하지 않았다.
- 미완료·다음 Codex: 남은 고위험 14개와 기타 55개를 실제 호출 경로·공급자 업데이트·AWS 권한/파일시스템 설정에 맞춰 검토한다. 보안 운영 판정은 보류하며 새 이미지는 아직 AWS에 업로드하지 않았다. 기존 AWS ECR 이미지와 모의 Secret/VPC/보안그룹은 보존했다. 이후 검증 이미지 업로드와 키움 AWS 허용 IP/추가 비용/온라인 진단/예약 비활성 배포를 진행한다. 현재 Docker 재빌드 성공을 키움 접속 또는 AWS 프로그램 배포 완료로 해석하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 호스트 전체 161개 및 이미지 프로그램 140개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 기존 모의 준비 자원/ECR 이미지 보존 / 새 보안 이미지 로컬 검증 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.

### 2026-10-14 00:35 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 기준 `main` / `bb5946e`. AGENTS.md → PC-C 단독 인수인계 → 공동 인수인계를 검토하고 기존 미커밋 작업을 보존했다. pull/commit/push 없음.
- 요청 흐름: Docker 취약점 검토를 시작한 뒤 사용자가 우선 로컬 Docker 컨테이너·이미지·볼륨 전체 삭제를 요청했다. 실제 삭제 대상과 예전 MySQL 데이터 포함 여부를 확인받았으며 사용자가 `MySQL 데이터 포함 전부 삭제`를 명시적으로 승인했다.
- 삭제 완료: 로컬 `desktop-linux` 컨텍스트의 컨테이너 4개, 고유 이미지 15개(태그·표시 항목 16개), 볼륨 50개를 삭제했다. 실행 직전 목록이 검토한 스냅샷과 같은지 대조했고, 정확한 ID/볼륨 이름만 대상으로 삭제했다. 컨테이너에는 정지된 docker8 서버/PHP/MySQL/artisan이 포함됐고 볼륨 중 MySQL `/var/lib/mysql` 데이터도 사용자 승인 범위에 포함됐다. 최종 재조회 결과 컨테이너 `0`, 이미지 `0`, 볼륨 `0` 확인.
- 보존 범위: C:/Test 프로젝트와 기존 미커밋 작업, AWS ECR 저장 이미지·Secret·VPC·보안그룹을 변경하지 않았다. Docker 네트워크/빌드 캐시 전체 정리나 WSL 초기화는 요청 범위에 추가하지 않았다. 로컬 `stock-automation:dev`와 ECR에서 내려받았던 이미지도 삭제됐으므로 로컬 실행하려면 재빌드 또는 승인된 ECR 이미지 다운로드가 필요하다. 이전 ECR 업로드 검증 기록은 과거 확인 결과로 유지한다.
- 취약점 검토 진행 내용:
  - Docker Scout 상세 명령은 외부 서비스로 SBOM/패키지 메타데이터가 전달될 수 있다는 자동 승인 검토 사유로 거부돼 실행되지 않았다. 사용자에게 이유를 설명했고 사용자는 `외부 전송 없이 검토`를 선택했다. Scout 재시도나 다른 스캐너를 통한 이미지 메타데이터 전송도 하지 않는다.
  - 대안으로 공식 Grype `v0.120.1` Windows 바이너리를 runtime에 내려받아 공개 checksum SHA256 일치를 확인했다. 공개 DB 다운로드만 시도했고 자동 앱 업데이트/외부 데이터 조회를 껐으나, 사용자 삭제 요청을 우선하며 다운로드 프로세스를 중단했다. 취약점 스캔 완료 또는 DB 확보 성공으로 보고하지 않는다.
  - 삭제 전 네트워크 차단·읽기 전용 컨테이너에서 런타임 Python 패키지를 확인했다. urllib3 `2.8.0`, boto3/botocore `1.43.111` 등이 확인됐으며 msgpack/setuptools는 런타임 배포 목록에 없었다. 사용자 Scout 화면의 urllib3 `2.7.0`/msgpack/setuptools 항목과 차이가 있으므로 개별 CVE/레이어/분석 범위를 추가 대조해야 한다. 이 사실만으로 35건이 해결됐다고 판단하지 않는다.
- Docker 장애: 실제 컨테이너 생성과 이미지/컨테이너 조회에 HTTP 500이 재발했다. `AutoPause: false` 상태를 확인하고 정상 `docker desktop restart` 성공 후 컨테이너 패키지 조회와 삭제 작업을 완료했다. 복구 도구의 cp949 출력 표시 오류는 있었지만 restart 종료 코드는 0이다. 장기 재발 원인과 근본 해결은 미검증이다.
- 변경 파일: 이 공동 인수인계; Git 제외 `runtime/docker-cleanup-inventory.json`, `runtime/delete_docker_inventory.py`, `runtime/docker-cleanup-result.json`, `runtime/security-tools/` 바이너리/checksum/미완료 DB 캐시. Dockerfile/의존성/매매 로직은 변경하지 않았다.
- 검증 결과: 이번 작업에서 전체 unittest `161개 통과`. 삭제 전 컨테이너 패키지 조회 성공, 삭제 스크립트 preview 및 검토 목록 대조 성공, 삭제 후 세 자원 목록 0개 확인, runtime Git 제외 및 `git diff --check` 통과.
- 미완료·다음 작업: 외부 메타데이터 전송 없이 공개 취약점 DB와 로컬 새 이미지로 CVE/수정 버전을 검토한다. 새 빌드 시 이미 완료한 ECR 저장소/Secret 준비를 중복 생성하지 않는다. 키움 AWS 허용 IP·추가 비용·온라인 API 진단·프로그램 배포는 계속 미완료다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의 준비 자원과 ECR 이미지 보존 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.

### 2026-10-14 00:26 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 기준 브랜치/커밋: `main` / `bb5946e`. 이전 미커밋 작업을 보존했다. 이번 작업 중 pull, commit, push 없음.
- 사용자 승인: 사용자가 `ㄱㄱ`로 비공개 ECR 저장소 1개 생성과 검증 이미지 1개 업로드를 승인했다. 안내한 보관료는 약 $0.01~$0.02/월이며 기존 모의 Secret 3개 비용 승인도 유지한다. 서버·유료 고정 IP·NAT Gateway·프로그램 배포·예약 실행의 승인은 포함하지 않는다.
- 실제 완료 범위:
  - 지정 IAM `stock-paper-operator`, 서울 리전으로 비공개 `stock-automation` ECR 저장소를 생성했다. AES256 암호화, 태그 불변 `IMMUTABLE`, push scan 비활성 설정을 확인했다.
  - 기존 `stock-automation:dev` 이미지를 내용 기반 태그로 업로드했다. ECR 조회에서 이미지 1개와 OCI manifest를 확인했다. ECR가 보고한 저장 크기는 `110,773,704 bytes`이다. 이전 기록의 로컬 inspect 크기와 Docker Desktop 화면의 `472.76 MB`는 측정 항목이 다르므로 이를 모두 동일한 비압축 크기로 해석하지 않는다.
  - 업로드 후 원격 digest로 이미지를 다시 내려받았다. 원본과 다운로드 이미지의 RootFS 레이어 목록이 일치했다. linux/amd64 및 비관리자 사용자 `65534:65534` 확인. 네트워크 차단·읽기 전용·cap-drop ALL·no-new-privileges 컨테이너에서 프로그램/정적 파일 36개 해시 일치, 키움/boto3 import 및 CLI help 검증 통과.
  - ECR 인증값은 프로세스 메모리와 password-stdin으로 전달하고 Docker Desktop native credential helper를 사용했다. 임시 Docker config에는 평문 auth가 없음을 확인하고 임시 디렉터리를 정리했다. 키·토큰·계정 ID·레지스트리 URI 원문을 공유 문서/출력에 기록하지 않았다.
- 실패·복구·검증 한계:
  - Docker push는 manifest PUT 단계 HTTP 400으로 종료 코드 1을 반환했고 동일 태그 재시도도 실패했다. 그 후 ECR에서 실제 저장된 이미지를 조회하고 digest 다운로드·레이어·소스·실행을 검증한 결과 업로드 산출물은 확인됐다. 명령 자체를 성공했다고 기록하지 않는다. manifest config digest와 로컬 image ID 비교도 불일치했으므로 이 비교만으로 이미지 일치를 주장하지 않는다. HTTP 400의 정확한 원인은 미확정이며 태그 불변 정책을 해제하지 않았다.
  - 재부팅 이후에도 준비 중 Docker image inspect/컨테이너 실행에서 HTTP 500이 재발했다. Docker Desktop을 정상 종료하고 기존 settings-store.json 원본을 옆 파일에 백업한 뒤 `AutoPause: false`를 적용, 정상 시작 후 엔진 응답과 이미지 검증을 복구했다. Resource Saver가 관여했을 가능성은 추정이며 장기 재발 방지는 미검증이다. WSL 디스크 초기화·등록 해제·강제 프로세스 제거는 하지 않았다.
  - 사용자 Docker Scout 화면에서 취약점 35건을 확인했다. urllib3, msgpack, setuptools 및 Debian 패키지 항목이 보인다. 개별 CVE, 수정 가능 버전, 실제 영향은 아직 검토하지 않았으며 운영 전 검토할 항목이다. 이미지 일치/CLI 검증을 보안 감사 완료로 해석하지 않는다.
- 변경 파일: 이 공동 인수인계 기록, Git 제외 `runtime/ecr-upload-plan.json`, `runtime/ecr-repository.json`, `runtime/ecr-upload-result.json`; 프로젝트 외 로컬 Docker Desktop 자동 일시정지 설정과 원본 백업. 기존 정책·설정 도구·테스트는 이번 작업에서 수정하지 않았다.
- 검증 결과: 재부팅 후 전체 unittest `161개 통과` 및 compileall 통과 기록 유지. 이번 작업은 프로그램 코드 변경 없이 ECR 저장/다운로드/레이어/36개 파일/CLI 검증을 추가했다. runtime 정보 Git 제외와 문서 `git diff --check` 통과. 계정/토큰 원문이 포함된 runtime 파일을 stage하지 않는다.
- 남은 과제: 운영 전 취약점 세부 검토와 필요한 이미지 갱신, 키움 허용 IP를 만족하는 짧은 예약 실행 구조와 추가 비용 검토, 온라인 키움/OpenDART 진단, 텔레그램 실제 발송, 프로그램 스택 및 모의 예약 실행 배포. 현재 키움 허용 IP는 PC IP이므로 ECR 업로드만으로 AWS API 접속이 준비된 것은 아니다.
- 다음 Codex의 첫 작업: 세 파일 인수인계와 실제 상태를 다시 대조한다. Git 제외 업로드 결과의 `UPLOADED_AND_VERIFIED` 및 digest를 활용하고 저장소를 중복 생성하지 않는다. 운영 전 취약점과 고정 접속 IP 제약을 검토하고 실행 구조·비용·정책을 구체화한 뒤 필요한 추가 승인만 받는다. 승인된 ECR/Secret 준비를 반복 확인하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret·VPC·보안그룹·ECR 이미지 준비 / 프로그램 스택 미배포 / 예약 비활성`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.

### 2026-10-14 00:05 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 요청 목표: Windows 재부팅 후 Docker/WSL 복구를 확인하고 중단했던 ECR 업로드 준비를 재개.
- 완료한 작업:
  - AGENTS.md → PC-C 단독 인수인계 → 공동 인수인계 순서로 검토하고 실제 Git 상태와 Docker 설정을 대조했다. 기준 `bb5946e`, 이전 세션의 미커밋 9개 파일이 유지됐고 알 수 없는 새 변경이나 pull은 확인되지 않았다. 이전 작업을 보존하고 실거래 비활성 검증을 이어간다고 알렸다.
  - WslService `Running`, Docker Engine 실제 API 버전 `28.0.1` 응답 확인. 기존 이미지 `stock-automation:dev`가 남아 있고 크기는 `110,776,565 bytes`(약 111 MB, 비압축 로컬 크기), 플랫폼 linux/amd64, 사용자 `65534:65534` 확인. 이전 WSL StopPending/이미지 조회 시간 초과는 재부팅 후 재현되지 않았다.
  - 네트워크 차단·읽기 전용·권한 제거 일회성 컨테이너에서 CLI help 및 키움/boto3 import 검증. 이미지의 프로그램 소스·정적 자산 36개 해시를 현재 워크스페이스와 대조해 모두 일치했다.
  - 이미지 환경변수에 지정한 앱키/AWS키/텔레그램키/실거래 활성화 변수가 없음을 확인하고 소스의 AWS access key·텔레그램 토큰 형태에 대한 제한된 패턴 검사 통과. 전체 보안 감사나 키 유효성 검증을 완료했다는 의미는 아니다.
  - 지정 IAM 사용자/서울 리전 STS 확인 통과. ECR DescribeRepositories 결과 저장소 `stock-automation`은 아직 없다. 원문 신원·계정 ID·키 값은 출력하지 않았다.
  - Git 제외 `runtime/ecr-upload-plan.json` 작성. 비공개 `stock-automation` 저장소 1개, 검증한 이미지 ID, 내용 기반 태그 `paper-bb5946e-<image-id-prefix>`, AES256 암호화·태그 불변·push scan 비활성 계획이다. 실제 AWS 생성/업로드는 하지 않았다. Docker 기본 native credential helper 실행 파일 존재를 확인했으며 인증값을 평문 프로젝트 파일에 저장하지 않는 업로드 방식을 사용한다.
- 전체 테스트 결과: 재부팅 후 unittest `161개 통과`, compileall 통과. 컨테이너 CLI/import/소스 일치 검사와 `git diff --check` 통과. runtime 계획의 Git 제외 확인.
- 변경 파일: 이 공동 인수인계와 Git 제외 업로드 계획. 프로그램 소스·기존 도구·정책·테스트는 변경하지 않았다.
- 비용 검토: 공식 ECR 가격 예시 $0.10/GB/월 기준 현재 이미지 1개의 보관료는 비압축 크기로 계산하면 약 $0.011/월, 안내 범위 $0.01~$0.02/월. 실제 ECR 압축 보관량·무료 혜택·크레딧·세금에 따라 차이가 있다. https://aws.amazon.com/ecr/pricing/ 에서 저장 요금과 같은 리전 AWS 서비스 전송 무료 안내를 재확인했다. 다른 서버·네트워크 자원 비용을 포함한 총 운영비 추정이 아니다.
- 사용자 승인 상태: 기존 모의 Secret 3개 생성 승인은 유지. ECR 저장소 생성과 검증 이미지 1개 업로드의 비용 승인은 이번 응답에서 별도 요청할 단계다. 승인을 받기 전 CreateRepository·ECR 로그인·push를 하지 않는다.
- 다음 Codex의 첫 작업: 사용자가 ECR 생성/이미지 1개 업로드를 승인하면 위 계획을 사용해 전용 IAM 프로필로 수행한다. native credential helper와 password-stdin으로 인증값을 보호하고 원문 계정 ID/레지스트리 URL/토큰을 일반 출력하지 않는다. 최종 이미지 digest와 저장량을 검증하고 Git 제외 배포 정보에 기록한다. 승인된 범위를 반복 확인하지 않는다.
- 미완료 사항: ECR 업로드, 키움 허용 IP를 만족하는 AWS 예약 실행 방식·추가 비용 검토, 온라인 키움/OpenDART 진단·메신저 실제 발송·프로그램 스택 배포.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 기존 모의용 Secret·VPC·전용 보안그룹 유지 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, 로컬 기록만 추가, commit/push하지 않음.

### 2026-10-13 23:55 KST — PC-C → 재부팅 후 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 사용자 화면과 실제 실패: 사용자 Docker Desktop 화면은 처음 `Engine running`이었지만 실제 엔진 version/image inspect가 각각 25초 제한 시간 초과했고, Docker 내부 WSL 명령도 8초 제한 시간 초과했다. 이후 사용자가 `Docker Desktop - Unexpected WSL error` 화면을 제공했다. 메시지는 WSL 배포판 목록 조회 `context deadline exceeded`로, 애플리케이션 키 오류가 아니라 Docker/WSL 실행환경 오류로 좁혀졌다.
- 수행한 복구:
  - 일반 Docker Desktop CLI restart를 시도했으나 실패했다. 이 조회 도구의 Python cp949 출력 디코딩 오류도 발생했으며 이후 명령은 원시 bytes를 캡처해 그 오류를 피했다. 실제 Docker 복구 성공으로 보고하지 않는다.
  - WSL 실행 중 목록 명령도 시간 초과돼 HKCU WSL 등록 정보에서 이름을 출력하지 않고 개수만 확인했다. Docker용 배포판 1개, 그 외 사용자 Linux 배포판 0개 확인.
  - Docker Desktop CLI stop은 성공했다. 이어서 `wsl --shutdown`은 20초 제한 시간 초과했다.
  - 다른 등록 Linux 환경이 없는 상태에서 WslService 정상 재시작을 시도했으나 종료 대기에서 멈췄다. 장시간 대기하는 명령은 Ctrl+C로 중단했고 최종 실제 서비스 상태는 `StopPending`이다. PC 재부팅을 사용자에게 안내한다.
- 보존한 내용: 프로젝트 파일, WSL 배포판과 Docker 디스크 데이터를 삭제·초기화·등록 해제하지 않았다. Docker/WSL 재설치, 전체 PC 자동 재부팅, VM 강제 프로세스 제거는 하지 않았다. 새 AWS 자원 생성·이미지 업로드·실제 주문 없음.
- 현재 AWS 준비 완료 범위: IAM operator 로그인, 모의용 Secret 3개 실제 생성, 전용 VPC/공개 서브넷 2개/인바운드 없는 전용 보안그룹, Secret/네트워크/ECR 준비 권한. ECR 조회 권한 적용 확인까지 완료됐지만 저장소 자체는 아직 없다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 기존 미커밋 정책 3개·로컬 설정 도구·테스트를 보존했다. Git 제외 runtime 정보도 보존한다.
- 검증: 문서 `git diff --check` 통과. 프로그램 코드 변경이 없어 테스트 반복 없음(직전 전체 `161개 통과`). Docker 이미지 용량·실행 재확인은 미완료다.
- 다음 Codex의 첫 작업:
  1. 사용자가 열려 있는 작업을 저장한 후 Windows 재부팅을 수행하고 Docker Desktop을 다시 열었는지 확인한다.
  2. AGENTS.md와 두 인수인계를 읽고 기존 미커밋 작업을 보존한다. `StockPaperEcrUpload`를 다시 만들거나 이미 승인된 Secret 비용 승인을 반복하지 않는다.
  3. WslService 실행 및 Docker Engine 실제 API 응답을 읽기 전용으로 확인한다. `stock-automation:dev` 이미지가 남아 있으면 용량/플랫폼/비관리자 설정을 확인하고, 필요한 경우 승인된 기존 Docker 빌드를 재실행한다.
  4. 업로드할 이미지를 구체적으로 검증한 뒤 ECR 보관 비용과 생성·업로드 범위를 사용자에게 승인받고 전용 IAM 프로필로 진행한다. ECR 비용은 아직 승인 대기다.
- 남은 과제: ECR 저장소 생성·이미지 업로드, 키움 허용 IP를 만족하는 예약 실행 구조·추가 비용 검토, 온라인 키움/OpenDART 진단, 실제 메신저 발송 및 프로그램 스택 배포. 현재 범위는 분석·모의매매/종가배팅 예약 우선이며 상시 단타를 추가하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret·VPC·전용 보안그룹 준비 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음. 공식 복구 참고: https://learn.microsoft.com/en-us/windows/wsl/basic-commands , 사용자 제공 Docker 오류 화면의 WSL 종료/PC 재부팅 안내.

### 2026-10-13 23:43 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 사용자 작업: 고객 관리형 `StockPaperEcrUpload` 정책 생성 및 `stock-paper-operator`에 직접 연결 완료 보고. 준비한 ECR 정책 JSON과 이름을 안내했고 사용자의 정책 검토 화면에서도 이름/ECR 서비스를 확인했다.
- 실제 AWS 확인: 해당 IAM 프로필/서울 리전으로 `stock-automation` 저장소 DescribeRepositories를 호출해 `RepositoryNotFoundException` 확인. 조회 권한이 적용됐으며 저장소는 아직 없다. 실제 생성·인증 토큰 발급·업로드 권한은 해당 작업 수행 전까지 미검증이다. 계정 ID·ARN·비밀정보를 출력하지 않았다.
- Docker 점검: `docker desktop status`는 RUNNING. 기존 `stock-automation:dev` image inspect는 20초 제한 시간 초과. Docker 환경변수 HOST/CONTEXT override 없음, 현재 context desktop-linux, 로컬 named pipe, docker-desktop WSL 실행을 확인했다. WslService 실행 중. com.docker.service/LxssManager는 stopped였으나 이것만으로 Linux WSL 엔진 장애 원인이라고 단정하지 않는다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 기존 미커밋 작업 보존.
- 검증: 읽기 전용 권한·Docker 연결 대상 확인 및 문서 `git diff --check` 통과. 코드 변경 없어 테스트 반복 없음(직전 전체 `161개 통과`). 실제 Docker 컨테이너/서비스 재시작·종료·제거는 하지 않았다.
- 다음 Codex의 첫 작업: 사용자가 Docker Desktop 창의 엔진 상태 문구를 확인하게 하고 일시정지/Resource Saver/정상 실행 중 여부를 구분한다. 앱 RUNNING과 Docker Engine 정상 응답은 같은 의미가 아니다. Docker 공식 Resource Saver·CLI 상태 안내를 검토했다. 이미지 조회/실행을 정상화한 후 크기·비밀정보 미포함·재현성 검사를 마치고 ECR 업로드 비용 및 범위 승인을 받는다.
- 승인 대기: ECR 이미지 보관/업로드는 아직 비용 승인받지 않았다. 저장소/이미지를 생성하지 않는다. 기존 Secret 비용 승인은 보존한다.
- 미완료 사항: Docker 이미지 용량·실행 재확인, ECR 비용 승인·저장소 생성·업로드, 키움 고정 접속 IP 구조·추가 비용, 온라인 API 진단·프로그램 배포.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret·VPC·전용 보안그룹 준비 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 23:34 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업:
  - 사용자 전용 보안그룹 생성 보고 후 지정 IAM 사용자로 새 VPC의 `stock-automation-paper-task`를 조회했다. 정확히 1개이며 인바운드 규칙 0개, 모든 IPv4 아웃바운드 허용 확인. Git 제외 `runtime/aws-network-inventory.json`에 보안그룹 ID와 검사 결과를 추가했다. 사용자 화면의 이름·설명·VPC·규칙과도 대조했다.
  - 다음 ECR 준비를 위해 `stock-automation/infra/paper-ecr-upload-policy.json` 작성. 서울 리전에서 인증 토큰 발급과 `stock-automation` 저장소 1개 생성·이미지 업로드/조회/다운로드만 허용한다. IAM 변경·삭제·배포·실주문 권한은 추가하지 않았다.
  - 기존 두 인라인 정책의 로컬 compact JSON 길이는 1140+369=1509자, 새 ECR 정책까지 합치면 2190자로 사용자 인라인 정책 누적 한도 2048자를 초과한다. 따라서 ECR 권한은 사용자 인라인 추가가 아니라 별도 고객 관리형 정책 `StockPaperEcrUpload`을 만들고 연결하는 방식으로 안내한다. 실제 AWS 저장 정책의 재작성된 길이는 조회하지 않았으므로 이 수치는 준비 파일 기준이다.
- 변경 파일: ECR 정책 JSON, 이 공동 인수인계, Git 제외 runtime 정보. 기존 미커밋 작업 보존.
- 검증: ECR 정책 JSON·작업/저장소/리전 범위 검사 통과, 전체 unittest `161개 통과`, `git diff --check` 통과. 공식 ECR 업로드 IAM 안내 https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html 와 IAM 관리형 정책 생성/크기 한도 안내를 확인했다.
- 비용 참고: ECR 공식 가격 예시에서 보관료 $0.10/GB/월과 같은 리전 AWS 서비스로의 전송료 $0.00/GB를 확인했다. 실제 이미지 크기 확인 후 비용과 생성·업로드 범위를 안내해야 한다. https://aws.amazon.com/ecr/pricing/
- 실패·미확인 사항: Docker Desktop/backend 프로세스는 실행 중이나 `docker image inspect stock-automation:dev`가 응답하지 않아 해당 조회만 Ctrl+C로 중단했다. 이미지 용량 재확인 미완료. Docker 서비스/컨테이너를 재시작하거나 제거하지 않았다. 직전 이미지 빌드 성공 기록은 과거 검증 결과로 보존한다. ECR 정책 실제 등록·저장소 생성·업로드는 미실행이다.
- 다음 Codex의 첫 작업: 사용자 관리자 콘솔 IAM 왼쪽 정책 → 정책 생성 → JSON 화면을 열게 하고 위 파일로 고객 관리형 `StockPaperEcrUpload` 정책을 만든 뒤 `stock-paper-operator`에 연결한다. 이어서 Docker 응답·기존 이미지 확인 문제를 해결하고 업로드할 이미지를 구체화한 후, 별도 ECR 비용 승인을 받고 전용 IAM 프로필로 진행한다. Secret 3개 비용 승인만으로 ECR/서버 생성까지 승인된 것으로 해석하지 않는다.
- 남은 과제: 키움 허용 IP를 만족하는 AWS 예약 실행 구조·추가 비용 검토, 온라인 API 진단·실제 메신저 발송·프로그램 스택 배포. 상시 단타·항상 켜진 서버를 기본으로 추가하지 않는다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret·VPC·전용 보안그룹 준비 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 23:04 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 사용자 작업: VPC 생성 화면에서 이름 자동 생성 `stock-automation-paper`, IPv4 `10.77.0.0/16`, IPv6 없음, 기본 테넌시, AZ 2개, 공개 서브넷 2개, 비공개 서브넷 0개, NAT 없음, VPC 엔드포인트 없음, DNS 두 옵션 체크를 안내했다. 사용자가 생성 완료를 보고했다. DNS 두 옵션 체크는 사용자 화면에서도 확인했다.
- 실제 AWS 확인: 지정 IAM 사용자와 서울 리전으로 조회해 이름 접두사·CIDR가 일치하는 VPC 1개를 특정하고 `available` 상태를 확인했다. 서브넷 2개가 서로 다른 AZ에 있고 둘 다 활성 인터넷 게이트웨이 기본 경로를 갖는다. NAT 경로 없음, 탄력 IP 0개, 해당 VPC 보안그룹 1개 확인. 기존 가이드에서 요구하는 공개 서브넷의 기반이 마련됐다.
- 검증 한계: 현재 조회 정책에는 DescribeVpcAttribute/DescribeNatGateways/DescribeVpcEndpoints가 없어서 DNS 실제 속성과 NAT/엔드포인트 전체 목록은 직접 조회하지 않았다. 사용자 설정 안내 및 화면 확인과 실제 원격 조회 결과를 구분한다. NAT 경로가 없다는 사실만으로 모든 NAT 자원이 없다고 단정하지 않는다.
- 로컬 준비 정보: Git 제외 `runtime/aws-network-inventory.json`을 선택한 VPC·서브넷의 ID/AZ/라우팅 정보로 갱신했다. 키·계정 ID·공인 IP 원문은 넣지 않았다.
- 변경 파일: 이 공동 인수인계, Git 제외 runtime 정보. 기존 정책·도구·테스트 미커밋 변경 보존.
- 검증: AWS VPC/서브넷/라우팅 조회 및 Git 제외 확인 통과. 코드 변경 없이 문서 `git diff --check` 통과. 직전 전체 unittest `161개 통과`.
- 다음 Codex의 첫 작업: 사용자 VPC 콘솔 → 보안 그룹 → 보안 그룹 생성 화면을 열게 한다. 새 VPC에 전용 `stock-automation-paper-task` 보안그룹을 만들고 인바운드 규칙은 비워둔다. 외부 API 통신과 SSM/ECR 등을 고려한 아웃바운드를 구체화하고 생성 후 원격 조회로 검증한다. 그다음 키움 허용 IP를 해결할 예약 실행 구조와 비용을 구체화한다.
- 미완료 사항: 전용 보안그룹, 고정 접속 IP 구조 및 비용 승인, 배포 권한, 온라인 API 진단·메신저 실제 발송·프로그램 스택 배포. VPC 생성만으로 키움 AWS 접속이 완료된 것은 아니다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret 및 VPC 네트워크 준비 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:57 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업: 사용자 `StockPaperNetworkInspect` 생성 완료 보고 후 지정 IAM 사용자로 서울 리전 EC2 조회 작업 7개를 수행했다. 전부 통과했다. VPC `0개`(기본 VPC 없음), 인터넷 게이트웨이 `0개`, 보안그룹 `0개`, 탄력 IP `0개`, 종료되지 않은 EC2 인스턴스 `0개`를 확인했다. 이 결과는 서울 리전만 대상으로 하며 다른 리전의 자원이나 전체 AWS 청구액을 확인한 것은 아니다.
- 로컬 준비 정보: `runtime/aws-network-inventory.json`에 정리했으며 `git check-ignore`로 Git 제외를 확인했다. 키·계정 ID·IP 주소는 포함하지 않는다. 이번 조회에서는 기본 VPC가 없어 선택한 서브넷도 없다.
- 변경 파일: 이 공동 인수인계만 추가 변경. Git 제외 runtime 파일 생성. 기존 미커밋 정책·도구·테스트 변경 보존.
- 검증: IAM 신원 확인 후 AWS 네트워크 읽기 통과, 저장 정보 집계 대조, Git 제외 및 `git diff --check` 통과. 코드 변경 없음으로 테스트 반복 없음(직전 전체 `161개 통과`).
- 다음 Codex의 첫 작업: 사용자 AWS 콘솔의 서울 리전 VPC 대시보드를 열도록 안내하고 새 네트워크 구성 준비를 진행한다. 기존 VPC가 있다고 가정한 가이드 명령을 그대로 실행하지 않는다. AWS 모의 실행에 필요한 서브넷·라우팅·인바운드 없는 보안그룹을 구체화한다. 키움 허용 IP에 맞는 고정 접속 방식도 해결해야 하며 승인 없이 NAT Gateway·EC2·탄력 IP 등 유료 자원을 생성하지 않는다.
- 미완료 사항: 새 네트워크 생성 권한/구성, 고정 접속 IP 구조·비용 검토, 프로그램 배포 권한, 온라인 API 진단 및 모의 스택 배포. 무료/유료 자원 모두 이번 조회에서는 생성하지 않았다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret만 생성 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:54 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 사용자 보고: 키움 모의 App Key 관리 화면의 IP 등록 상태는 마지막 정정 기준 현재 PC의 IP `1개 등록`. 앞선 `0개` 응답을 최신 상태로 취급하지 않는다. IP 원문은 받거나 저장하지 않았다.
- 네트워크 검토: 현재 CloudFormation은 Fargate 작업별 `AssignPublicIp: ENABLED`이며 실행마다 같은 공인 IP를 보장하는 구성이 아니다. 키움 허용 IP 등록과 AWS 접속을 해결하기 전에는 예약 활성화나 배포 완료로 보고하지 않는다. AWS 공식 설명 https://docs.aws.amazon.com/AmazonECS/latest/developerguide/networking-outbound.html 확인. 고정 IP·NAT·EC2 등 새로운 유료 자원은 아직 생성하지 않았다.
- 완료한 작업: 서울 리전에서 기존 VPC·서브넷·라우팅·보안그룹·인터넷 게이트웨이·탄력 IP·인스턴스 정보만 읽을 수 있는 `stock-automation/infra/paper-network-inspect-policy.json` 준비. Create/Modify/Delete·키 원문 읽기·실거래·배포 권한은 없다. 실제 IAM 부착은 사용자 대기 중이다.
- 변경 파일: 위 정책 JSON과 이 공동 인수인계. 이전 미커밋 변경 보존.
- 검증: 정책 JSON 파싱·조회 작업 7개와 서울 리전 한정 조건 검사 통과. 전체 unittest `161개 통과`, `git diff --check` 통과. 실제 AWS 네트워크 조회는 정책 부착 후 진행한다.
- 다음 Codex의 첫 작업: 사용자가 관리자 콘솔 IAM → `stock-paper-operator` → 권한 → 인라인 정책 생성 → JSON 화면을 열도록 안내한다. 위 파일 내용으로 `StockPaperNetworkInspect` 정책을 추가한 뒤 지정 IAM 사용자로 네트워크를 읽기 전용 확인한다. 그 결과를 바탕으로 종가배팅 예약 작업의 고정 접속 방식과 비용을 구체화한다. 별도 승인 없이 고정비 인프라를 생성하거나 상시 단타를 구현하지 않는다.
- 실패·미확인 사항: AWS 네트워크 구성, 키움 모의 API에서 IP 제한의 실제 응답, 온라인 키 검증·실제 메신저 발송·배포 권한·프로그램 배포 모두 미확인.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret만 생성 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:48 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업: 사용자 업로드 완료 보고 후 `stock-paper-operator`/서울 리전에서 모의용 세 이름의 DescribeSecret을 다시 실행했다. 키움 모의·OpenDART·텔레그램 모두 정확한 이름·삭제 대기 아님·AWSCURRENT 버전 존재를 확인했다. 세 항목 `CREATED_ACTIVE_CURRENT`. Secret 원문을 읽거나 출력하지 않았다.
- 승인·비용 상태: 앞선 사용자 승인 범위의 모의용 Secret 3개 생성 완료를 확인했다. 다른 인프라 생성이나 예약 활성화는 하지 않았다. 보관료는 앞선 $1.20/월 + API 사용료 안내 조건이며 생성 시점 이후 실제 사용 기간·세금·크레딧 등에 따라 청구된다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 기존 미커밋 작업 보존.
- 검증: 실제 AWS 세 항목 메타데이터 확인 통과. 코드 변경 없어 테스트 반복 없음(직전 전체 `161개 통과`), 문서 `git diff --check` 통과. 저장 확인은 내용 및 API 키 유효성 검증과 다르다.
- 접속 IP 검토: 공식 키움 서비스 이용안내 https://openapi.kiwoom.com/intro/serviceInfo 에서 허용된 IP에서만 인증, IP 최대 10개 등록 및 실전/모의 App Key 관리 탭 구분 안내를 확인했다. 현재 사용자의 모의 App Key 관리 화면에서 실제 IP 설정 표시를 확인한 후 AWS 접속 방식과 비교해야 한다. 기존 Fargate 공인 IP 변동 문제는 미해결이며 고정 IP 인프라를 임의로 생성하지 않는다.
- 다음 Codex의 첫 작업: 사용자가 키움 REST API 사이트의 모의투자 App Key 관리 화면을 열고 IP 등록 현황 표시 여부를 확인하게 한다. 키·계좌번호·IP 원문을 대화로 요구하지 않는다. 확인 후 짧게 실행하는 AWS 모의 작업의 접속 구조와 비용을 구체화한다. 상시 단타/항상 켜진 EC2를 기본 범위로 확대하지 않는다.
- 실패·미확인 사항: 키움/OpenDART 키 실제 온라인 유효성, AWS에서의 모의 API 인증, 메신저 실제 발송, 배포 권한 및 모의 스택 배포 미완료.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 모의용 Secret만 생성 / 프로그램 스택 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:46 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 사용자 승인: 서울 리전에 모의용 Secret 3개를 생성하는 작업과 보관료 합계 약 월 $1.20 + API 사용료(세금·크레딧 등에 따른 차이)를 안내했고, 사용자가 `ㄱㄱㄱ`으로 진행을 승인했다. 승인 범위는 `stock-automation-paper/kiwoom-demo`, `/dart`, `/telegram` 생성이다. 이 승인으로 실거래·예약 활성화·다른 유료 배포까지 허용된 것으로 해석하지 않는다.
- 현재 상태: 업로드 도구 존재 확인. 사용자가 자신의 CMD에서 `upload_paper_secrets.py --create`를 실행하고 모의 App Key·모의 Secret·OpenDART 키를 숨김 입력할 단계다. 텔레그램 토큰·chat_id는 사용자 로컬 vault에서 자동으로 읽는다. 실제 생성 성공은 아직 확인하지 않았다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 이전 미커밋 작업 보존.
- 검증: 코드 변경 없이 문서 `git diff --check` 통과. 직전 전체 테스트 `161개 통과`.
- 다음 Codex의 첫 작업: 사용자의 저장 완료 출력 또는 비밀정보 없는 오류 문구를 확인한다. 비용 승인을 다시 요구하지 않는다. 성공 시 DescribeSecret으로 세 항목 존재만 확인하고 비밀값을 읽거나 출력하지 않는다. 일부 생성 실패 시 기존 Secret을 덮어쓰거나 삭제하지 않고 원인과 남은 항목을 확인한다.
- 미완료 사항: 실제 AWS Secret 생성 확인, OpenDART 온라인 조회, 키움 온라인 doctor, 메신저 실제 발송, 키움 허용 IP 검토 및 모의 배포.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 직전 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:44 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업:
  - 사용자 보고로 IAM 인라인 정책 `StockPaperSecretSetup` 생성 완료. `stock-paper-operator`로 모의용 세 이름의 DescribeSecret을 실제 호출해 모두 `ResourceNotFoundException`을 확인했다. 조회 권한 적용 및 미생성 상태 확인이며 생성 권한의 실제 검증은 아직 아니다. 비밀값·ARN·계정 ID는 읽거나 출력하지 않았다.
  - `tools/upload_paper_secrets.py` 작성. 사용자 직접 실행 시 지정 IAM 사용자/서울 리전을 확인하고 세 이름이 모두 없는지 먼저 검사한다. 키움 모의 키 2개와 OpenDART 키를 숨김 입력받고, 텔레그램은 사용자 로컬 Windows vault에서만 읽어 세 Secret을 생성한다. 기존 Secret 덮어쓰기와 자동 삭제는 하지 않는다.
  - CLI의 기본 실행은 안내만 출력하며, 실제 생성에는 `--create`가 필요하다. SDK 호출에는 비밀값을 메모리로 전달하고 명령 인수·평문 임시 파일·일반 로그에 기록하지 않는다. AWS 기본 관리형 암호화키를 사용하며 복제·회전·새 KMS 키를 추가하지 않는다.
  - AWS 브라우저 로그인 지원에 필요한 `botocore[crt]`와 boto3 버전 조건을 도구 전용 requirements에 추가·설치했다. Python SDK에서 해당 IAM 사용자 STS 확인도 통과했다. 에이전트는 업로드 도구의 실제 생성 경로를 실행하지 않았다.
- 변경 파일: `stock-automation/tools/upload_paper_secrets.py`, `stock-automation/tools/requirements.txt`, `stock-automation/tests/test_paper_secret_upload.py`, 이 공동 인수인계. 이전 도구·정책·테스트 로컬 변경 보존.
- 검증 결과: 신규 도구 집중 테스트 `9개 통과`, 전체 unittest `161개 통과`, Python compileall, CLI help 및 생성 없는 기본 실행 확인, `git diff --check` 통과. 가짜 응답으로 root 차단·기존 항목/권한 오류 중단·계약 필드·오류 비노출·부분 실패 보존·비대화형 실행 차단을 확인했다.
- 비용 검토: AWS 공식 Secrets Manager 가격 페이지의 일반 가격 예시 기준 저장료 $0.40/개/월, 3개 유지 시 $1.20/월, API $0.05/10,000회 추가. 세금·사용 기간·크레딧 등에 따른 실제 청구 차이가 있다. 근거: https://aws.amazon.com/secrets-manager/pricing/
- 실패·미확인 사항: 유료 Secret 3개 생성에 대한 사용자 승인 대기. 실키 입력·생성·저장 완료 확인·OpenDART 온라인 조회·메신저 실제 발송·배포 모두 미실행. SDK의 CRT 의존성 누락은 설치 후 해결했다.
- 남은 위험: 생성 도중 일부만 성공하면 완료 항목은 유지되며 이후 호출을 중단한다. 재실행은 기존 항목을 발견해 중단하므로, 일부 성공 시 원인을 확인하고 별도로 나머지 항목을 처리해야 한다. Secret 입력이 실제 키움 모의 키인지 사용자 확인이 필요하다. 키움 허용 IP/변동 IP 문제와 배포 권한도 미완료다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`, `LIVE TESTS: 전체 161개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 다음 Codex의 첫 작업: 서울 리전 모의용 Secret 3개 생성 비용 승인을 받는다. 승인 후 사용자 CMD에서 `.venv/Scripts/python.exe stock-automation/tools/upload_paper_secrets.py --create`를 실행하도록 안내한다. 키 값은 사용자 터미널에만 입력하고 대화로 받지 않는다. 승인 없이 생성하지 않는다.
- 전달 파일 버전: 기준 `bb5946e`, 로컬 준비만 수행, commit/push하지 않음.

### 2026-10-13 22:37 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 요청 목표: 사용자 IAM 권한 화면에서 모의용 비밀정보 저장 권한 준비.
- 완료한 작업: 로컬 `stock-automation/infra/paper-secret-setup-policy.json` 작성. 서울 리전의 `stock-automation-paper/kiwoom-demo`, `/dart`, `/telegram` 세 이름에 한해 CreateSecret/DescribeSecret/PutSecretValue를 허용하도록 제한했다. 조회·갱신은 자기 계정 조건을 적용하고 이름 뒤 ARN 6자리 무작위 접미사는 `??????`로 한정했다. 키 원문 읽기·목록 조회·삭제·IAM 변경·배포 권한은 추가하지 않았다.
- 변경 파일: 정책 JSON과 이 공동 인수인계. 기존 도구·테스트 미커밋 변경 보존.
- 검증: AWS 공식 Secrets Manager 서비스 권한 및 IAM 인라인 정책 문서 확인. JSON 파싱, 허용 작업 3개·이름 3개·리전·다른 실거래/유사 이름 불일치 등 로컬 범위 검사 통과. 전체 unittest `152개 통과`, `git diff --check` 통과.
- 실패·미확인 사항: 실제 IAM에 정책을 부착하지 않았다. AWS 콘솔 정책 검증과 실제 권한 동작은 미확인이다. Secrets Manager 자원 생성·키 업로드·배포·과금 자원 생성은 하지 않았다.
- 다음 Codex의 첫 작업: 사용자 권한 탭에서 권한 추가 → 인라인 정책 생성 → JSON 화면을 열게 한 뒤 준비한 정책을 안내한다. 정책 이름은 `StockPaperSecretSetup`. 기존 로그인·비밀번호 변경 정책을 보존한다. 실제 Secret 생성 전에 비용·생성 범위를 안내하고 사용자 승인을 확인한다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 통합검증 미완료`, `LIVE TESTS: 전체 152개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, 로컬 준비만 수행, commit/push하지 않음.

### 2026-10-13 22:33 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업: 사용자 AWS 재로그인 성공 보고 이후, `stock-paper-operator`/`ap-northeast-2`로 읽기 전용 STS 호출을 수행하고 ARN의 지정 IAM 사용자 일치 여부만 확인했다. 결과 `EXPECTED_IAM_USER`. 계정 번호·ARN 원문·인증값은 출력하거나 문서에 기록하지 않았다.
- 실제 코드·문서 검토: 기존 AWS 실행 가이드와 템플릿에서 모의용 키움·OpenDART·텔레그램 Secret 계약을 확인했다. 기존 사용자 정책 기록은 로그인·암호변경용 2개뿐이며, Secret 등록 및 배포 권한을 추가로 준비해야 한다. 현재 정책을 IAM API로 재조회한 것은 아니다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 기존 미커밋 도구·테스트 변경 보존.
- 검증 결과: AWS IAM 로그인 확인 통과, 문서 `git diff --check` 통과. 코드 변경 없음으로 테스트 반복 없음(직전 전체 `152개 통과`).
- 실패·미확인 사항: Secret 등록 권한과 AWS 배포 권한 미준비. 실제 Secret 등록·알림 발송·온라인 doctor·AWS 모의 배포는 미실행. 키움 허용 IP 문제도 미해결이다.
- 다음 Codex의 첫 작업: 사용자가 기존 관리자 콘솔에서 IAM → 사용자 → `stock-paper-operator` → 권한 화면을 열도록 안내하고, 프로젝트 모의용 Secret에 한정한 정책을 준비한다. 관리자 프로필로 배포하거나 광범위한 AdministratorAccess를 부여하지 않는다. Secret 생성 비용과 유료 인프라는 실제 생성 전 사용자 확인이 필요하다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 통합검증 미완료`, `LIVE TESTS: 직전 전체 152개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:28 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 완료한 작업: 사용자 CMD 출력에서 텔레그램 등록 도구의 `등록 완료`를 확인했다. 도구가 봇·개인 대화방을 조회한 후 토큰과 chat_id를 Windows 자격 증명 저장소(service `stock-automation-setup`, account `telegram`)에 저장한 상태다. 에이전트는 실제 저장 값이나 비밀 파일을 읽지 않았다. 실제 메시지 발송 및 AWS 연결은 아직 하지 않았다.
- AWS 확인 결과: `stock-paper-operator` 프로필로 읽기 전용 STS 인증 확인을 수행했으나 재로그인이 필요했다. 계정 ID·ARN 원문·오류 원문을 출력하지 않았고 다른 프로필로 우회하지 않았다.
- 변경 파일: 이 공동 인수인계만 추가 변경. 기존 도구·테스트 로컬 변경 보존.
- 검증: 사용자 실제 등록 성공 출력 확인. 코드 변경이 없어 테스트를 반복하지 않았다. 직전 전체 테스트는 `152개 통과`이며 문서 `git diff --check` 통과.
- 실패·미확인 사항: AWS operator 로그인 만료. 배포 권한·Secrets Manager 연결·OpenDART 온라인 조회·키움 온라인 doctor·모의 AWS 통합검증은 미완료. 유료 인프라 생성 없음.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 통합검증 미완료`, `LIVE TESTS: 직전 전체 152개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 다음 Codex의 첫 작업: 사용자 터미널에서 `aws login --profile stock-paper-operator --remote` 실행을 안내한다. IAM 사용자로 인증 후 STS에서 지정 사용자임을 비밀정보 없이 재확인하고 최소권한·모의용 Secret 연결 준비를 진행한다. 토큰이나 인증 코드는 대화로 요청하지 않는다.
- 전달 파일 버전: 기준 `bb5946e`, commit/push하지 않음.

### 2026-10-13 22:26 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`, 작업 경로: `C:/Test`.
- 요청 목표: 사용자 CMD에서 텔레그램 등록 도구 실행 시 발생한 연결·응답 오류 해결.
- 확인한 실패: 사용자 실행은 숨김 토큰 입력 이후 연결 실패했다. 에이전트가 토큰 없이 공개 `api.telegram.org/` 경로를 조회했을 때 Python 기본 TLS에서 `SSLCertVerificationError`, 검증 코드 19가 재현됐다. 인증서 신뢰 문제를 확인했으며 토큰 유효성은 아직 미확인이다.
- 완료한 작업:
  - Windows 네이티브 신뢰 저장소를 사용하는 `truststore.SSLContext(PROTOCOL_TLS_CLIENT)`를 등록 도구에 적용했다. 인증서·호스트명 검증을 유지하며 전역 SSL 설정이나 시스템 인증서 저장소를 변경하지 않는다.
  - 도구 전용 의존성 `tools/requirements.txt`를 추가하고 PC-C `.venv`에 설치했다. AWS 런타임 의존성과 배포 코드는 변경하지 않았다.
  - 인증서·DNS·시간초과·HTTP 401/409 오류를 비밀정보 없는 문구로 구분했다. CMD 직접 실행 안내도 반영했다.
  - 수정된 도구와 동일한 TLS context로 공개 경로 HTTPS 연결 성공(302 응답)을 확인했다. 응답 리다이렉트는 따라가지 않았으며 토큰·대화 내용·chat_id를 읽거나 출력하지 않았다.
- 변경 파일: `stock-automation/tools/setup_telegram.py`, `stock-automation/tools/requirements.txt`, `stock-automation/tests/test_telegram_setup.py`, 이 공동 인수인계. 기존 로컬 변경과 이전 기록을 보존했다.
- 테스트 결과: 도구 집중 테스트 `12개 통과`, 전체 unittest `152개 통과`, Python compileall 및 `git diff --check` 통과. 인증서·호스트명 검증 유지와 오류 정보 비노출을 검사했다.
- 실패·미확인 사항: 실제 토큰으로 사용자 재실행 필요. 텔레그램 등록 완료, 실제 메시지 발송, AWS Secret 연결 및 OpenDART 온라인 검증은 아직 확인하지 않았다. AWS operator 재로그인·배포 권한·키움 허용 IP 문제도 미해결이다.
- 남은 위험: 공개 경로 연결 성공만으로 실제 봇 토큰이 유효하다고 판단하지 않는다. PC-D에서 도구를 쓰려면 도구 전용 requirements 설치가 필요하다.
- 실거래 상태: `LIVE CODE SAFETY: 미완성 / 통합검증 미완료`, `LIVE TESTS: 전체 152개 통과 / 실제 체결 미검증`, `LIVE AWS DEPLOYMENT: 이번 세션 미배포`, `LIVE ORDER SUBMISSION: 없음`, `KILL SWITCH: 기본 ON 설계 / 원격 상태 미확인 / 해제하지 않음`.
- 다음 Codex의 첫 작업: 사용자가 CMD에서 같은 등록 명령을 재실행한 결과를 확인한다. 실패하면 개선된 오류 문구만 요청하고 자격 증명 값은 요구하지 않는다.
- 전달 파일 버전: 기준 `bb5946e`, 로컬 변경만 존재. commit/push하지 않았다.

### 2026-10-13 21:22 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`
- 작업 경로: `C:/Test`
- 요청 목표: OpenDART 인증키 준비 및 텔레그램 개인 알림 대화방 등록 준비를 한 단계씩 진행.
- 완료한 작업:
  - 사용자 보고 기준으로 OpenDART 승인과 인증키 파일의 프로젝트 외부 보관을 완료했다. 키 원문을 읽거나 API 유효성을 검증하지 않았다.
  - 사용자 보고 기준으로 Telegram 가입, BotFather에서 개인 알림 봇 생성, 토큰 외부 보관, 해당 봇에 `/start` 전송을 완료했다.
  - `stock-automation/tools/setup_telegram.py`를 추가했다. 사용자가 직접 실행하고 숨김 입력으로 토큰을 제공하면 공식 `getMe`/`getUpdates` 조회만 수행한다. 지정한 봇과 개인 `/start` 대화방이 하나인지 확인하고 `bot_token`/`chat_id` JSON을 Windows 자격 증명 저장소에 함께 저장한다.
  - 저장 위치의 service는 `stock-automation-setup`, account는 `telegram`이다. 실제 자격 증명 값을 대화·Git·프로젝트 파일·출력에 기록하지 않는다. AWS Secret 등록은 아직 하지 않았다.
  - 그룹·여러 개인 대화방·다른 봇 토큰을 거절한다. 기존 로컬 등록 교체는 사용자 터미널에서 `yes` 확인이 필요하다. 평문 keyring 대체 백엔드를 허용하지 않는다.
  - 메시지 발송, webhook 수정, getUpdates offset 변경을 하지 않는다. 리다이렉트와 원시 오류 출력도 금지한다.
- 변경 파일: `stock-automation/tools/setup_telegram.py`, `stock-automation/tests/test_telegram_setup.py`, 이 공동 인수인계. 앞선 20:58 로컬 기록을 보존했다.
- 추가·변경 테스트: 가짜 자격 증명으로 조회 전용 메서드, 개인 대화방 선택, 잘못된 토큰·봇 차단, 오류 비밀정보 노출 방지, 비대화형 실행 차단 등 10개 통과.
- 전체 테스트 결과: `150개 통과`(기존 140개 + 신규 10개). Python compileall, 도구 `--help`, Windows vault 백엔드 사용 가능 여부 확인 통과.
- 실패·미확인 사항: 사용자 실제 토큰으로 등록 도구 실행은 대기 중이다. OpenDART 실제 조회·텔레그램 실제 알림 발송·AWS Secrets Manager 연결·온라인 doctor·AWS 모의 통합검증은 미실행이다. AWS operator 프로필은 앞선 확인에서 재로그인이 필요했다.
- 남은 위험: getUpdates에 `/start`가 없으면 다시 전송 후 재실행해야 한다. 개인 대화방이 여러 개면 자동 선택하지 않는다. AWS 배포 권한과 키움 허용 IP/변동 공인 IP 문제는 해결되지 않았다. 신규 유료 인프라는 생성하지 않았다.
- 실거래 상태:
  - `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`
  - `LIVE TESTS: 전체 unittest 150개 통과 / 실제 주문·체결 통합검증 미실행`
  - `LIVE AWS DEPLOYMENT: 이번 PC-C 세션에서 미배포 / 기존 원격 자원 유무 미확인`
  - `LIVE ORDER SUBMISSION: 이번 세션 없음`
  - `KILL SWITCH: 기본 ON 설계 / 실제 테이블 상태 미확인 / 해제하지 않음`
- 다음 Codex의 첫 작업: 사용자 PowerShell의 등록 완료 또는 비밀정보 없는 오류 문구를 확인한다. 토큰과 chat_id를 대화로 요구하지 않는다. 완료 후 AWS operator 재로그인과 최소권한·모의용 Secret 연결 준비를 순서대로 진행한다.
- 사용자에게 확인받을 사항: 본인 PowerShell에서 등록 도구 실행 결과만 확인. 실제 토큰 입력은 사용자가 수행한다.
- 전달 파일 버전 또는 Git 커밋: 기준 `bb5946e`, 위 파일은 로컬 변경 상태. 이번 세션에서 commit/push하지 않았다.

### 2026-10-13 20:58 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`
- 작업 경로: `C:/Test`
- 요청 목표: 사용자가 완료한 pull에서 PC-D 추가 작업을 확인하고 전날 중단한 AWS 모의운영 준비를 재개.
- 완료한 작업:
  - `main`의 기준 `bb5946e`(병합 충돌 해결 커밋), 앞선 PC-D 커밋과 공동 인수인계를 대조했다. 시작 시 작업 폴더는 깨끗했고 기준 문서에서 미해결 충돌 표시는 발견되지 않았다.
  - `AGENTS.md`의 추가 Git 인수인계 규칙, PC-C 7.8 우선 검증 절차, 공동 전달 기록을 확인하고 작업 전 안전 경계 확인 문구를 알렸다.
  - 대표 README, Codex 환경 가이드, 연속 단타 설계·비용 문서, 주식 분석 보고서와 이벤트 CSV의 추가를 확인했다. 주식 보고서는 과거 기록으로만 확인했으며 이번 세션의 신규 추천이나 체결을 생성하지 않았다.
  - 전날 PC-C의 `.gitignore`, `.dockerignore`, 패키징 수정 및 작업 기록이 병합 후 보존되어 있음을 확인했다.
  - `stock-automation/src`, `tests`, `infra`에는 전날 기준 `291ffdf` 대비 추가 변경이 없었다. 연속 단타 EC2 기능은 설계만 존재하며 미구현·미배포 상태다.
  - Python 전체 테스트와 구문 검사를 재실행했다. 꺼져 있던 Docker Desktop을 실행하고 이미지를 다시 빌드했다.
  - 키움 CLI 읽기 전용 진단에서 `pc-c-demo`, 서버 `demo`, 인증정보·토큰 존재, 호출 가능, 특이 사항 없음을 확인했다. 새 온라인 시세 요청이나 주문은 실행하지 않았다.
  - AWS IAM 프로필의 STS 확인은 임시 로그인 재인증 필요로 실패했다. 계정번호·키·토큰 및 원본 인증 출력은 노출하지 않았고 루트 프로필로 우회하지 않았다.
  - OpenDART 공식 사이트에서 인증키 신청/관리 메뉴를 확인했다. 사용자의 키 신청·등록은 다음 단계로 안내한다.
- 변경 파일: `Codex_세션간_공동_인수인계.md` (이번 기록 추가만). 엔진·전략·안전장치 코드 변경 없음.
- 추가·변경 테스트: 새 테스트 없음. pull 후 필수 회귀검증을 재실행.
- 전체 테스트 결과: `140개 통과`, `compileall` 통과.
- 수동 검증 결과: Docker 이미지 `stock-automation:dev` 빌드 성공, 키움 CLI 진단 통과, 시작 시 Git clean 및 문서 충돌 표식 검사. 작업 변경의 `git diff --check`도 확인한다.
- 실패·미확인 사항:
  - `stock-paper-operator` AWS 로그인 재인증 필요. 재로그인 완료 후 기대한 IAM 사용자·서울 리전을 다시 확인해야 한다.
  - OpenDART 키, 프로그램의 종합 `doctor --online`, 텔레그램 및 AWS 자원 배포·통합검증은 아직 미완료.
  - 연속 단타의 문서상 비용은 추정값이며 구현 승인이나 실제 과금 확인을 뜻하지 않는다. EC2·고정 IP를 생성하지 않았다.
  - 기존 아키텍처 문서의 실주문 코드 미존재 등 일부 설명은 현재 코드·최신 전달 기록과 다르므로 과거 요약으로 취급한다.
- 남은 위험: Fargate 발신 IP와 키움 허용 IP를 배포 전 해결·검증해야 한다. 모의운영 완료를 로컬 테스트 통과만으로 판단하지 않는다.
- 실거래 상태:
  - `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`
  - `LIVE TESTS: 전체 unittest 140개 통과 / 실제 주문·체결 통합검증 미실행`
  - `LIVE AWS DEPLOYMENT: 이번 세션 미배포 / 기존 원격 자원 유무 미확인`
  - `LIVE ORDER SUBMISSION: 이번 세션 없음`
  - `KILL SWITCH: 기본 ON 설계 / 실제 테이블 상태 미확인 / 해제하지 않음`
- 다음 Codex의 첫 작업: OpenDART 인증키 준비를 사용자에게 한 단계씩 안내하고, AWS 작업 전 `aws login --profile stock-paper-operator --remote` 재인증을 완료해 IAM 신원을 재확인한다. 비밀값을 대화로 요청하지 않는다.
- 사용자에게 확인받을 사항: OpenDART 인증키를 이미 보유했는지 또는 신청 화면을 열었는지 확인. 별도 연속 단타·유료 인프라·실거래 승인 없음.
- 전달 파일 버전 또는 Git 커밋: `main`, 기준 `bb5946e`; 이번 기록만 로컬 변경. commit/push 미실행. 이전 기록 순서는 병합 결과 그대로 보존했다.

### 2026-10-12 20:38 KST — PC-C → 다음 PC-C / PC-D

- 작업 PC alias: `PC-C`
- 작업 경로: `C:/Test`
- 요청 목표: 다른 PC에서 제작한 프로그램을 C 드라이브에서 검증하고 AWS 모의운영을 단계별로 준비. 이번 PC-C 세션의 누적 준비 결과를 기록한다.
- 완료한 작업:
  - 전체 Markdown 및 두 인수인계 문서를 확인하고 Git 기준 커밋 `291ffdf`와 실제 파일을 대조했다.
  - Docker Desktop 실행, AWS CLI v2 설치, Python 3.13 추가 설치를 완료했다. Python 3.14는 유지했다.
  - 비어 있던 키움 공식 라이브러리 폴더를 준비하고 지정 커밋 `234560d213acd8871ae344b5481aecd2f30287fa`로 고정했다.
  - `C:/Test/.venv`에 Python 3.13 프로그램 환경과 의존성을 설치했다.
  - 사용자 승인 후 중복 wheel 포함 설정을 제거해 로컬 설치와 Docker 빌드 오류를 해결했다.
  - 루트 `.gitignore`를 생성하고 `.dockerignore`를 보완했다. 인증정보, 가상환경, 외부 키움 저장소, 캐시, 실행 결과를 Git 또는 Docker 입력에서 제외하고 소스·투자 기록·필수 빌드 입력은 유지했다.
  - 등록용 공식 `kwcli` 1.0.3을 `.venv/kiwoom-cli` 별도 환경에 설치했다. 기존 엔진 환경의 키움 버전은 변경하지 않았다.
  - 사용자가 모의투자를 신청하고 모의계좌·IP를 등록한 뒤 모의 App Key/Secret을 본인 PowerShell의 숨김 입력으로 등록했다. Codex는 비밀키 파일·키 값·클립보드를 읽지 않았다.
  - 초기 `8001` 인증 실패 후 일반 문자열 붙여넣기 시험은 `OK`였고, 사용자가 PowerShell을 다시 사용해 등록 성공을 알렸다. 정확한 최초 실패 원인은 확정하지 않았다.
  - 공식 CLI 읽기 전용 진단에서 별칭 `pc-c-demo`, 서버 `demo`, 인증정보 존재, 토큰 사용 가능, 호출 가능, 특이 사항 없음을 확인했다. 주문은 실행하지 않았다.
  - 사용자가 AWS 작업용 IAM 사용자 `stock-paper-operator`를 생성하고 콘솔 암호를 변경했다. 부여한 정책은 `SignInLocalDevelopmentAccess`, `IAMUserChangePassword`다.
  - CLI 프로필 이름만 IAM 이름이고 실제 인증은 루트였던 상태를 발견했다. 사용자가 `aws login --profile stock-paper-operator --remote`로 IAM 브라우저 세션에서 재인증했다.
  - 최종 STS 확인에서 기대한 IAM 사용자 일치, 루트 아님, CLI 인증 성공, 서울 리전 `ap-northeast-2`를 확인했다. 계정번호·키·토큰은 출력하지 않았다.
- 변경 파일:
  - `.gitignore` (신규)
  - `.dockerignore`
  - `stock-automation/pyproject.toml`
  - `Codex_세션간_공동_인수인계.md` (이번 기록 추가)
- 로컬 생성 항목: Git 제외 대상 `Kiwoom-REST-API/`, `.venv/`, Docker 이미지 `stock-automation:dev`. 키·토큰은 Git에 포함하지 않는다.
- 추가·변경 테스트: 새 테스트 코드 없음. 기존 전체 unittest, 설치 패키지 자산 검사, 네트워크 차단 컨테이너 검사, ignore 규칙 검증을 실행했다.
- 전체 테스트 결과:
  - 최초 실행: 138개 통과, 키움 명세 누락으로 테스트 그룹 초기화 오류 1건. 전체 통과로 보고하지 않았다.
  - 지정 키움 명세 확보 후: `140개 전체 통과`.
- 수동 검증 결과:
  - Python `3.13.16`, 기존 `3.14.7`, AWS CLI `2.37.12`, Docker 클라이언트/엔진 `28.0.1` 확인.
  - 패키징 수정 후 프로그램 설치와 `pip check` 통과, 설치된 CLI 도움말 확인.
  - ignore 수정 후 Docker 빌드 성공. Linux/amd64, 비루트 실행 사용자 `65534:65534` 확인.
  - `--network none` 일회성 컨테이너에서 CLI 실행, 키움·boto3 import, 대시보드 JS/HTML/CSS 포함 확인.
  - 키움 API 명세와 대시보드 자산 유지, 빌드 입력의 Git·가상환경·캐시 제외 확인.
  - `git check-ignore`로 환경·인증·실행 파일 제외와 소스·예제·투자 기록 보존 확인. `git diff --check` 통과.
  - 키움 CLI 진단과 AWS STS 읽기 전용 인증 확인 완료. 이번 세션에서 compileall·JavaScript 문법검사·브라우저 UI 검증은 별도로 실행하지 않았다.
- 실패·미확인 사항:
  - OpenDART 인증키 준비는 아직 시작하지 않았다.
  - 텔레그램 인증정보 준비·시험 알림, AWS 네트워크·Secret·ECR·CloudFormation 배포는 미실행이다.
  - 현재 IAM 사용자에게는 CLI 로그인·암호 변경 권한만 설정했다. AWS 자원 배포용 권한은 아직 준비하지 않았다.
  - 프로그램의 `stock-automation doctor --online` 종합 진단과 실제 AWS·키움 모의 통합검증, 5거래일 모의운용은 미완료다. 키움 CLI 등록 성공과 프로그램 전체 통합검증을 구분한다.
  - AWS 발신 IP와 키움 허용 IP의 일치, 예약 태스크 재실행 시 인증 가능 여부는 배포 전 검증이 필요하다. 고정비 인프라를 임의로 추가하지 않는다.
  - 문서 상단의 132개 테스트 및 일부 미구현 설명은 과거 요약이다. 최신 PC-D 전달 기록·현재 코드·이번 검증 결과를 우선한다.
  - 최상위에서 참조된 `주식_자동매매_사용자_준비_가이드.md`, `실거래_개발_후속_Codex_프롬프트.md`, `집에_가져갈_주식자동매매_파일목록.md`는 해당 경로에 없다.
- 남은 위험: 로컬 검사 통과는 AWS 운영 검증 완료가 아니다. 실제 비용 발생 배포, 모의예약 활성화 및 실거래는 각각 필요한 확인을 거친다. 실거래 안전센터의 실제 테이블 상태는 미확인이다.
- 실거래 상태:
  - `LIVE CODE SAFETY: 미완성 / 실제 통합검증 미완료`
  - `LIVE TESTS: 전체 unittest 140개 통과 / 실제 주문·체결 통합검증 미실행`
  - `LIVE AWS DEPLOYMENT: 이번 PC-C 세션에서 미배포 / 기존 원격 자원 유무 미확인`
  - `LIVE ORDER SUBMISSION: 이번 세션 없음`
  - `KILL SWITCH: 기본 ON 설계 / 실제 테이블 상태 미확인 / 해제하지 않음`
- 다음 Codex의 첫 작업: 사용자가 요청한 2026-10-13에 OpenDART 인증키 준비부터 한 단계씩 재개한다. AWS 명령은 검증된 `--profile stock-paper-operator --region ap-northeast-2`를 사용하며 권한 부족을 루트 프로필로 우회하지 않는다.
- 사용자에게 확인받을 사항: 다음 단계에서 OpenDART 키 보유 여부를 확인한다. 키 값은 대화로 요청하지 않는다. 사용자는 오늘 추가 준비를 멈추고 내일 이어가기로 했다.
- 전달 파일 버전 또는 Git 커밋: 기준 `291ffdf`, 위 파일은 로컬 변경 상태. 이번 세션에서 commit/push하지 않았다. 이후 작업자는 기존 변경을 보존한다.
### 2026-10-13 14:53 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 2026-10-13 장중 현재 자료로 오늘의 신규 추천 종목과 자금 배분 판단
- 결론: `NO_TRADE` — 추천 0종목, AI 모의 투자금 0원, 현금 601,400원 100%
- 완료한 작업:
  - 열린 AI 실시간 모의 포지션이 없음을 먼저 확인
  - 14:52 KST 지수, 시장 폭, 기관·프로그램 잠정 수급과 양 시장 상승 종목을 새로 스크리닝
  - 금호전기·라온시큐어·국제약품·녹십자엠에스·HLB글로벌을 상대강도 관찰 대상으로 검토했으나 시장 충격, 과열 또는 촉매·NXT·분봉 지지 미확인으로 전부 제외
  - 실시간 분석 보고서와 프로그램 학습용 `NO_TRADE` 이벤트 기록
- 변경 파일:
  - `docs/실시간 데이터 확인/2026-10-13_1452_korean-stock-analysis.md`
  - `docs/프로그램 설계/추천_이벤트_현재본.csv`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 코드 변경 없음
- 전체 테스트 결과: 이번 추천 기록에서는 미실행; 직전 README 작업에서 140개 통과
- 수동 검증 결과: CSV 68건·28열 스키마 일치, 불량 행·중복 이벤트 ID 없음, `git diff --check` 통과
- 실패·미확인 사항: 후보별 호가잔량, 확정 기관·프로그램 수급, NXT 여부와 당일 촉매 미확인
- 남은 위험: KOSPI -5.81%, KOSPI 프로그램 약 -2조 2,745억원 잠정, 양 시장의 광범위한 하락과 기술적 반등 재실패 위험
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: 사용자가 종가배팅을 명시적으로 요청하면 15:20 KST 최신 KRX 자료로 별도 최종 판단하고 모의 결과를 기록
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-13 14:48 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: GitHub 저장소 첫 화면에서 자동매매 프로젝트의 목적, 현재 상태, 실행 환경과 안전 경계를 확인할 수 있도록 대표 README 작성
- 완료한 작업:
  - 저장소 루트에 GitHub 첫 화면용 `README.md` 신규 작성
  - 종가배팅·중기·단타·연속 단타·대시보드·실거래의 현재 상태를 구현·검증·설계 단계로 분리
  - 키움 모의 API부터 AWS 작업, 전략 엔진, DynamoDB·S3, 대시보드까지의 구조도 추가
  - PC-C PowerShell·Docker 시작 명령과 PC-D/PC-C 역할, 주요 문서 링크 추가
  - 실거래 비활성화, 비상정지 기본 ON, 기존 보유종목 보호와 비밀정보 금지 원칙을 첫 화면에 명시
- 변경 파일:
  - `README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 코드 변경 없음
- 전체 테스트 결과: `140개 통과`, `python3 -m compileall -q src tests` 통과
- 수동 검증 결과: README의 6개 로컬 링크 대상 존재 확인, `git diff --check` 통과
- 실패·미확인 사항: GitHub 원격 화면의 Mermaid 렌더링과 링크 이동은 push 후 브라우저에서 확인 필요
- 남은 위험: PC-C의 Docker·키움 모의·AWS 통합검증과 모바일 외부 접속 배포는 아직 완료되지 않음
- 실거래 상태: `비활성화 / 비상정지 기본 ON / NXT 비활성화 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 pull 후 세 기준 문서와 실제 Git 상태를 다시 확인하고 140개 테스트부터 재검증
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-13 11:26 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 단타 연속 감시의 AWS 구성, 키움 API 제약, 예상 월비용과 PC-C 후속 작업을 문서에 정리
- 완료한 작업:
  - 현재 `DAY_TRADE_ON_DEMAND`가 단발 모의 스캔이고 연속 감시는 미구현임을 명확히 구분
  - 향후 KST 08:50~16:00 EC2 세션, 09:00~15:30 감시, 14:50 신규 진입 중지, 15:10 의무 청산 구조 기록
  - 전체 종목 저빈도 선별 후 100개 이하 후보·20~50종목 실시간 정밀 감시 방식 기록
  - `t3.medium`, `gp3 20GB`, 고정 공인 IPv4 기준 월 22,000~27,000원과 30,000원 상한 기록
  - 현재 Fargate 가변 공인 IP와 키움 등록 IP의 충돌 위험, 연속 EC2와 기존 작업의 중복 실행 방지 원칙 기록
  - 연속 세션 상태기계, 장애 안전중지, 재시작 대사, 구현·모의검증 순서 기록
- 변경 파일:
  - `docs/프로그램 설계/연속_단타_AWS_운영설계_및_예상비용.md`
  - `docs/프로그램 설계/AWS_프로그램_아키텍처.md`
  - `stock-automation/README.md`
  - `AWS_자동매매_실행가이드.md`
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 문서만 변경하여 코드 테스트는 실행하지 않음
- 수동 검증 결과: 현재 코드의 `DAY_TRADE_ON_DEMAND`, CloudFormation의 Fargate `AssignPublicIp: ENABLED`, README와 인수인계의 단발 범위를 실제 파일과 대조
- 실패·미확인 사항: EC2 연속 프로세스, 고정 IP, 시작·종료 자동화와 키움 모의 연속 세션은 미구현·미배포·미검증
- 남은 위험: AWS 실제 가격·환율·키움 API 제한은 구현 시점에 다시 확인해야 하며, 기존 Fargate와 연속 EC2를 함께 켜면 중복 판단·비용이 발생할 수 있음
- 실거래 상태: `비활성화 / 비상정지 기본 ON / NXT 비활성화 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 우선 140개 테스트·Docker·키움 모의 읽기·스케줄 비활성 AWS 배포를 검증하고, 별도 구현 승인이 있기 전에는 연속 단타 EC2를 생성하지 않음
- 사용자에게 확인받을 사항: 향후 연속 단타 구현 착수 시점과 EC2 월 30,000원 예산 상한의 최종 승인
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-13 11:06 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 2026-10-13 급락장에서 종목을 매수하지 않는 판단이 타당한지 현재 시장 자료로 점검
- 결론: `NO_TRADE`—AI 모의 투자금 0원, 현금 601,400원 100%
- 핵심 근거:
  - 11:06 KST 실시간 표시값 기준 KOSPI 5,990.20(-6.17%), KOSDAQ 810.70(-4.53%)
  - KOSPI 상승 53·하락 851, KOSDAQ 상승 153·하락 1,538의 광범위한 약세
  - 두 지수 모두 장중 저가 근처이고 KOSPI 프로그램 약 1조 2,738억원 순매도 잠정
- 모의 포지션 점검: `실시간_모의투자_현재본.md`에 열린 포지션 없음; 조치할 보유 포지션 없음
- 변경 파일:
  - `docs/실시간 데이터 확인/2026-10-13_1106_korean-stock-analysis.md`
  - `docs/프로그램 설계/추천_이벤트_현재본.csv`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 보고서·CSV만 변경하여 코드 테스트는 실행하지 않음
- 수동 검증: 지수 실시간·시가·고가·저가·시장 폭·기관·프로그램 잠정치를 지수 API에서 교차 확인; 실시간 외국인 수급은 판단에 미사용; CSV 전체 67건의 28열 스키마·이벤트 ID 유일성 통과
- 기존 데이터 수정: 2026-10-06 NXT 관찰 3건의 초과 빈 컬럼을 제거해 29열에서 28열로 복구; 기존 판단·가격·메모 내용은 변경하지 않음
- 미확인 사항: 종목별 호가잔량, 확정 기관·프로그램 수급, 15:20 KST 시장 상태
- 남은 위험: 장중 잠정치는 달라질 수 있으며, 급락 후 단기 반등을 안정화로 오인하지 않아야 함
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: 15:20 종가배팅 요청을 받으면 시장 폭·지수·프로그램 흐름을 다시 확인하고 NXT 비대상만 신규 스크리닝
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-13 10:16 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: PC-D에서 새 기능을 추가하기 전에 PC-C가 현재 코드를 실제 키움 모의·AWS 환경에서 검증하도록 우선 작업과 완료 기준을 인수인계서에 추가
- 완료한 작업:
  - Git dirty·충돌 확인부터 AWS CLI 신원, 140개 테스트, Docker 빌드, 키움 모의 읽기 진단, 스케줄 비활성 AWS 배포·진단까지의 순서 고정
  - CloudWatch·S3·DynamoDB·텔레그램의 실행 ID·판단 대조를 예약 활성화 전 필수 조건으로 명시
  - 실패 시 예약 활성화를 중단하고, 비밀값을 Git·대화·로그에 남기지 않도록 경계 명시
  - 모의주문·단타 단발 실행·예약 활성화는 기준선 검증 후의 별도 단계로 분리
- 변경 파일:
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 문서만 변경하여 코드 테스트는 실행하지 않음
- 미확인 사항: PC-C의 실제 AWS CLI 인증, 140개 테스트, Docker, 키움 모의 온라인 진단, AWS 배포는 아직 명령 출력으로 검증되지 않음
- 남은 위험: AWS 콘솔 로그인을 AWS CLI 인증 완료로 오인하거나, 읽기 진단 전에 예약을 활성화하면 오류 원인을 분리하기 어려움
- 실거래 상태: `비활성화 / 비상정지 기본 ON / NXT 비활성화 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 pull 후 세 기준 문서와 실제 Git 상태를 다시 확인하고, 7.8의 체크리스트를 위에서부터 순서대로 수행
- 사용자에게 확인받을 사항: 실거래 활성화 요청 없음; 현재는 모의·읽기 전용 검증만 진행
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-13 09:55 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 2026-10-12 종가 시점에 매매했다면 선택했을 종목과 금액을 전일 마감 자료로 재구성
- 결론: `NO_TRADE`—종목 0개, 가정 자본 600,000원 중 투자금 0원, 현금 100%
- 핵심 근거:
  - KOSPI -3.65%, KOSDAQ -4.83%로 동반 급락하고 두 지수 모두 저가 근처 마감
  - 상승 353종목 대 하락 2,024종목의 광범위한 약세와 대규모 프로그램 순매도
  - 상대강도 후보 팬오션은 NXT 거래대상으로 최종 후보에서 필수 제외
  - 두산·두산우는 음봉 마감, 고가주, 유동성·손익비 미충족으로 제외
- 변경 파일:
  - `docs/종가배팅/2026-10-13_0952_korean-stock-analysis.md`
  - `docs/프로그램 설계/추천_이벤트_현재본.csv`
  - `Codex_세션간_공동_인수인계.md`
- 기록 경계: 10월 13일에 작성한 사후 가상 판단이므로 10월 12일 15:20 모의 체결을 소급 생성하지 않음
- 종가배팅 거래기록 엑셀: 실제·모의 체결이 없어 미반영
- 추가·변경 테스트: 보고서·CSV만 변경하여 코드 테스트 미실행. CSV 67행·28열 스키마와 신규 이벤트 ID 파싱 통과
- 수동 검증: 실시간 단타 모의 원장의 열린 포지션이 없음을 확인하고, 마감 지수·시장 폭·종목 일별 시세·NXT 여부를 외부 자료로 대조
- 미확인 사항: 10월 12일 15:20 정확 호가잔량, 5분봉, 종목별 확정 당일 기관·프로그램 수급은 미확인
- 남은 위험: 사후 분석을 어제 실제 체결로 오인하지 않아야 함
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: 현재 장 종가배팅을 요청받으면 15:20 KST에 실시간 재검증하고 NXT 비대상만 0~3종목 선정
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 15:40 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 현재 VS Code의 `/` 팔레트에 없는 `/fast`를 제외하고 슬래시 명령어 가이드를 현재 환경 기준으로 정정
- 완료한 작업:
  - 공식 OpenAI Remote/모바일 문서의 명령 목록이 VS Code와 항상 같지 않음을 명시
  - 판단 우선순위를 `현재 / 팔레트 → 설치 확장 → 공식 문서`로 정정
  - `/fast`를 사용 가능 명령 표에서 제거
  - 앞선 정정 대상인 `/side`와 `/fast`를 `현재 없는 명령`으로 분리
  - 기타 조건부 명령은 실제 `/` 팔레트에 보일 때만 사용하도록 정정
- 변경 파일:
  - `Codex_슬래시_명령어_최신가이드.md`
  - `Codex_세션간_공동_인수인계.md`
- 정정 사항: 바로 아래 `15:25 KST` 기록의 `/side`, `/fast` 사용 가능 명령 기재는 현재 VS Code 환경에 대해서는 잘못된 내용이며 이 기록으로 정정함
- 추가·변경 테스트: 문서만 변경하여 코드 테스트 미실행
- 문서 검증: 이번 변경 문서에 추가된 공백 오류 없음. 저장소 전체 `git diff --check`는 이번 작업과 무관한 `GorapaduckPet/bin`, `GorapaduckPet/obj`, `Test.sln` 등의 기존 CRLF 파일 때문에 실패
- 수동 검증 결과: 설치 확장 `openai.chatgpt-26.803.41515-win32-x64`의 명령 등록 정보와 공식 문서를 대조하고, 사용자가 제공한 현재 팔레트 정보를 최종 기준으로 반영
- 실패·미확인 사항: 확장 업데이트나 계정 기능 변경 후의 팔레트는 다시 확인 필요
- 남은 위험: 공식 Remote/모바일 자료를 VS Code 명령 목록으로 오인하지 않아야 함
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: 슬래시 명령 문서를 다시 갱신할 때는 현재 VS Code의 `/` 팔레트를 최우선 근거로 사용
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 15:25 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: PC-C Codex가 Git pull·push 때마다 인수인계와 안전규칙을 자동 확인하고 최신 `/` 명령어 가이드를 저장소에 보관
- 완료한 작업:
  - 루트 `AGENTS.md`에 PC-D·PC-C 역할과 Git 인수인계 상시 규칙 추가
  - 세션 시작과 모든 pull 후 `AGENTS.md`·PC-C 전체 인수인계·공동 인수인계를 다시 읽고 실제 코드와 비교하도록 의무화
  - PC-C가 작업 전 인수인계 확인과 실거래 비활성 유지를 명시적으로 알리도록 규칙 추가
  - dirty worktree·pull 충돌 시 변경을 버리지 않고 정확한 파일을 보고하도록 규칙 추가
  - 모든 push 전 선택적 staging, 관련·전체 테스트, 구문검사, `git diff --check`, 비밀정보 검사와 공동 인수인계 갱신 의무화
  - push는 사용자 요청 또는 승인 시에만 수행하고 성공 후 branch·commit을 보고하도록 규칙 추가
  - 현재 VS Code 확장과 Codex CLI 버전을 확인해 슬래시 명령어 최신 가이드 작성
  - 공식 OpenAI 문서 확인 명령과 현재 환경에서 확인된 `/usage`를 구분해 기록
  - `/status`, `/usage`, `/compact`, `/plan`, `/goal`, `/side`, `/review`, `/fork`, `/fast`, `/feedback`, `/plugins`의 용도와 프로젝트 사용 순서 정리
  - `/compact`가 파일 변경이나 사용 한도 초기화가 아니라는 주의사항 기록
- 변경 파일:
  - `AGENTS.md`
  - `Codex_슬래시_명령어_최신가이드.md`
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 문서·작업규칙 변경만 수행
- 전체 테스트 결과: 코드 변경 없음, 직전 `140개 통과` 유지
- 수동 검증 결과: 설치된 VS Code 확장 `26.803.41515`, `codex-cli 0.147.0-alpha.6.5` 확인 및 공식 OpenAI 자료 대조
- 실패·미확인 사항: 슬래시 명령 제공 여부는 확장·호스트·계정에 따라 달라질 수 있어 실제 `/` 팔레트를 최종 기준으로 사용해야 함
- 남은 위험: Codex가 실행되지 않은 상태에서 외부 Git pull·push를 실시간 감시할 수는 없으며 다음 대화 시작 시 `AGENTS.md` 규칙이 적용됨
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 pull 후 세 기준 문서를 다시 읽고 지정된 확인 문구를 출력한 다음 실제 Git 상태와 140개 테스트를 재검증
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 15:05 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 전문형 대시보드에 실거래 안전센터·주문 상태·모바일 UI 추가
- 완료한 작업:
  - 비상정지, 계좌 보호 기준선, 최근 체결·잔고 대사와 진행 주문을 모은 실거래 안전센터 추가
  - 대사 기록은 최근 10분 이내일 때만 정상으로 표시하고 누락·오래된 데이터는 확인 불가 처리
  - 실주문 환경변수·비상정지·보호 기준선·대사 상태를 네 개의 안전 게이트로 표시
  - 승인→전송→접수→체결/취소 주문 타임라인과 주문·체결·미체결 수량 표시
  - `SUBMITTING`, `CANCEL_SUBMITTING`, `UNCERTAIN`을 위험 상태로 표시
  - 계좌번호·계좌 별칭·계좌 지문이 대시보드 API에 노출되지 않도록 구성 및 테스트
  - 모바일 실행 이력을 표 대신 카드형으로 전환하고 홈·안전·포지션·이력 하단 메뉴 추가
  - `PAPER_TABLE`과 별도 `LIVE_ORDER_TABLE`을 읽기 전용으로 합치는 저장소 추가
  - 샘플 fixture에 비상정지·보호 기준선·부분체결 주문 예시 추가
  - UI의 실거래 설정과 비상정지 해제 기능은 계속 잠금 유지
- 변경 파일:
  - `stock-automation/src/stock_automation/dashboard.py`
  - `stock-automation/src/stock_automation/dashboard_static/index.html`
  - `stock-automation/src/stock_automation/dashboard_static/app.js`
  - `stock-automation/src/stock_automation/dashboard_static/styles.css`
  - `stock-automation/examples/dashboard_fixture.json`
  - `stock-automation/tests/test_dashboard.py`
  - `stock-automation/README.md`
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 모의·실거래 테이블 결합, 안전센터 정상/누락/불확실 상태, 개인정보 비노출, UI 자산·모바일 메뉴 존재 확인
- 전체 테스트 결과: `140개 통과`
- 수동 검증 결과: Python compileall, fixture JSON 구문, JavaScript 구문, 로컬 fixture API 응답, 변경 파일 공백 검사 통과
- 실패·미확인 사항: 실제 DynamoDB 두 테이블 연결과 브라우저 시각 회귀 확인은 PC-C에서 수행하지 않음
- 남은 위험: 모바일 외부 접속용 Cognito·HTTPS·감사로그 미구현; 실거래 테이블 읽기 IAM 권한도 PC-C에서 최소권한 검증 필요
- 실거래 상태: `비활성화 / 비상정지 기본 ON / UI 변경기능 잠금 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 140개 테스트와 fixture UI를 확인한 뒤 읽기 전용 `PAPER_TABLE`·`LIVE_ORDER_TABLE` 연결을 검증
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:52 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 현재 PC에서 가능한 실거래 안전 기능의 남은 코드 작업 진행
- 완료한 작업:
  - 키움 국내주식 취소주문 `kt10003`을 정확한 미체결 잔량으로 한 번만 호출하도록 구현
  - 주문 접수 시 최초 체결·잔량을 저장하고 누적 체결 증가분만 프로그램 포지션에 반영
  - 기본 180초가 지난 미체결 주문의 잔량 취소 상태 전이 추가
  - 취소 결과 불명확 시 자동 재시도 없이 `UNCERTAIN`으로 잠그고 비상정지하도록 구현
  - 재시작 시 접수·부분체결 주문을 재조회하고 `SUBMITTING` 등 모호한 상태는 추측하지 않고 비상정지
  - 실제 잔고와 `보호 기준선 + 프로그램 포지션`을 종목별 정확히 대사하고 불일치 시 비상정지
  - 주문번호 미조회·상태조회 실패·대사 실패도 비상정지하는 실패 폐쇄형 처리
  - 명시적 확인 문자열이 필요한 1회 실행 명령 `live-supervise` 추가
  - 상시 루프와 AWS 실거래 예약은 추가하지 않음
- 변경 파일:
  - `stock-automation/src/stock_automation/live_broker.py`
  - `stock-automation/src/stock_automation/live_execution.py`
  - `stock-automation/src/stock_automation/live_cli.py`
  - `stock-automation/src/stock_automation/cli.py`
  - `stock-automation/tests/test_live_broker.py`
  - `stock-automation/tests/test_live_execution.py`
  - `stock-automation/README.md`
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 취소 TR 요청값, 미체결 잔량만 취소, 취소 응답 불명확 잠금, 재시작 모호상태 비상정지, 보호 기준선과 프로그램 수량의 정확 대사
- 전체 테스트 결과: `137개 통과`
- 수동 검증 결과: Python compileall 통과, 전체 unittest 통과
- 실패·미확인 사항: 키움 실제/모의 API와 실제 DynamoDB를 이용한 주문취소·재시작·잔고대사 통합검증은 수행하지 않음
- 남은 위험: `live-supervise`는 실제 취소 요청이 가능한 명령이므로 PC-C 통합검증과 사용자 별도 승인 전 실행 금지; 실거래 전용 AWS 인프라·인증 UI·운영 주기는 아직 없음
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 137개 테스트를 재실행한 뒤 가짜/모의 환경으로 DynamoDB 상태 전이와 키움 취소 응답을 통합검증
- 사용자에게 확인받을 사항: 실거래 통합검증 단계에 들어가기 전 전용 계좌 여부와 감독형 소액 1건 승인
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:46 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: PC-D와 대화할 수 없을 때 PC-C와 새 Codex만으로 전체 작업을 계속할 수 있는 단일 인수인계 문서 작성
- 완료한 작업:
  - 새 Codex에게 그대로 전달할 PC-C 시작 프롬프트 작성
  - 안전 권한, 프로젝트 목적, 전략 분리, NXT·토스 제외 방침 정리
  - 현재 구현 기능, 132개 테스트 기준, DynamoDB 키 구조 정리
  - Git 확인부터 테스트·Docker·키움 모의·AWS 비활성 배포까지 실행 순서 작성
  - 단타 단발 실행, 15:50 총자산, AWS 예약표와 5거래일 검증 절차 정리
  - UI 외부 공개 제한, 현재 수동 배포 흐름과 CI/CD 미구현 상태 명시
  - 월 예상비용과 NAT Gateway·RDS·상시 서버 임의 추가 금지 기록
  - 실주문 가능 조건, 남은 개발 우선순위, 장애 중지 및 세션 종료 양식 작성
  - 공동 인수인계의 기준 문서 목록에 새 문서를 추가
- 변경 파일:
  - `PC-C_단독진행_전체인수인계.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 문서 변경만 수행
- 전체 테스트 결과: 코드 변경 없음, 직전 `132개 통과` 유지
- 수동 검증 결과: 495줄 문서 생성, 경로·금지 플래그·실행 단계 검색 및 `git diff --check` 통과
- 실패·미확인 사항: PC-C 실제 파일 복사·Git pull 및 새 Codex의 문서 읽기는 아직 확인하지 않음
- 남은 위험: 문서와 실제 코드가 달라질 때마다 PC-C Codex가 최신 상태로 갱신해야 함
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 새 전체 인수인계의 0절 프롬프트로 시작한 뒤 Git 상태와 132개 테스트 재검증
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:42 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: PC-C 실행 가이드에 실제 수행 항목이 모두 적혀 있는지 확인하고 최신 작업 반영
- 완료한 작업:
  - 다른 PC 실행 가이드에 15:50 일일 총자산 작업과 확인 명령 추가
  - 단타는 KST 09:10~14:50에 `DAY_TRADE_ON_DEMAND`로만 단발 실행하는 절차와 ECS 명령 추가
  - 단타 자동 스케줄 금지와 `paper_only`, 전용 DynamoDB 키 확인 항목 추가
  - 5거래일 CloudWatch·DynamoDB 원본 내보내기와 비밀정보 제외 요약 보고서 작성 절차 추가
  - PC-D가 확인할 수 있도록 운영 검증 보고서와 인수인계를 Git으로 전달하는 절차 추가
  - 실거래 검토 전 주문취소·미체결·재시작 복구·대사·자동 비상정지·인프라 분리 필수조건 명시
  - AWS 실행 가이드의 PC-C 경로를 `C:/Test`로 정정하고 NXT 비활성 방침 반영
- 변경 파일:
  - `다른_PC_프로그램_실행방법.md`
  - `AWS_자동매매_실행가이드.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 문서 변경만 수행, 실행 명령과 현재 CloudFormation 출력·환경변수 이름 대조
- 전체 테스트 결과: 코드 변경 없음, 직전 `132개 통과` 유지
- 수동 검증 결과: 문서 변경 범위 `git diff --check` 통과, PC-C 경로의 남은 `D:/Test` 표기 제거
- 실패·미확인 사항: AWS 콘솔과 실제 PC-C에서 명령을 아직 실행하지 않음
- 남은 위험: Windows PowerShell 및 실제 AWS 계정에서 단발 ECS 명령과 5일 자료 내보내기를 검증해야 함
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 가이드 순서대로 비활성 배포 후 온라인 진단을 실행하고 출력 기록
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:36 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 현재 PC에서 가능한 후속 구현과 실주문 가능 조건 정리
- 완료한 작업:
  - `DAY_TRADE_ON_DEMAND` 실행 단계를 추가해 명시적 단발 실행만 허용
  - 단타 스냅샷·결정을 S3에 남기고 전용 지갑·포지션·이벤트를 DynamoDB에 저장하도록 연결
  - 단타 자동 반복 스케줄은 만들지 않아 상시 장중 감시 금지 방침 유지
  - `EQUITY_SNAPSHOT_1550` 단계에서 모든 모의 지갑 현금과 열린 포지션의 검증 현재가를 합산
  - 현재가 누락·지연 시 일일 총자산을 기록하지 않는 실패 차단 유지
  - 15:50 일일 총자산 AWS Scheduler 항목 추가, `CoreScheduleState=DISABLED` 기본값 유지
  - CloudFormation에 단타 전용 초기 모의자금 환경변수 추가
- 변경 파일:
  - `stock-automation/src/stock_automation/aws_runtime.py`
  - `stock-automation/infra/cloudformation.yaml`
  - `stock-automation/tests/test_aws_runtime.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 단타 단발 AWS 저장 경로, 키움 확인가 기반 총자산 집계 및 일일 저장
- 전체 테스트 결과: `132개 통과`
- 수동 검증 결과: Python compileall, CloudFormation YAML 구문 로드, 변경 파일 범위 `git diff --check` 통과
- 실패·미확인 사항: 실제 AWS와 키움 모의 API 호출은 PC-C에서만 통합검증 가능
- 남은 위험: 실주문 취소·장시간 미체결·재시작 복구·주기적 대사·불일치 비상정지 및 실거래 전용 인프라가 미완성
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 모의 테이블로 `DAY_TRADE_ON_DEMAND`와 `EQUITY_SNAPSHOT_1550`을 수동 실행해 결과 확인
- 사용자에게 확인받을 사항: 5거래일 모의운용 완료 후 소액 실거래 전환을 별도로 승인할지 여부
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:32 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 현재 PC에서 가능한 DynamoDB 저장 계층 보완 및 PC-C 역할 확인
- 완료한 작업:
  - 단타 결정을 `DAY#` 이벤트로 저장하는 DynamoDB 함수 추가
  - 단타 매수 시 `OPEN#DAY_TRADE` 생성과 `WALLET#DAY_TRADE` 차감을 하나의 트랜잭션으로 묶음
  - 단타 `NO_TRADE`도 중복 방지 조건과 함께 이벤트로 보존
  - 모의·실거래별 일일 총자산을 `EQUITY#<MODE>#<날짜>`로 한 번만 저장하는 함수 추가
  - 모의 지갑 현금과 열린 포지션 평가액 집계 추가
  - 열린 포지션의 검증 현재가가 없으면 진입가나 0원으로 대체하지 않고 스냅샷 생성을 중단하도록 처리
- 변경 파일:
  - `stock-automation/src/stock_automation/aws_runtime.py`
  - `stock-automation/tests/test_aws_runtime.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 단타 BUY/NO_TRADE DynamoDB 저장, 전용 지갑 분리, 일일 총자산 합산, 미확인가 실패 차단
- 전체 테스트 결과: `130개 통과`
- 수동 검증 결과: Python compileall 통과, 이번 변경 파일 범위 `git diff --check` 통과
- 실패·미확인 사항: 실제 AWS 자격증명·테이블·키움 현재가를 사용한 통합실행은 이 PC에서 수행하지 않음
- 남은 위험: 단타 단발 명령과 실제 DynamoDB 호출 연결, 일일 평가용 키움 현재가 수집 및 AWS 예약 작업 연결 필요
- 실거래 상태: `비활성화 / 저장 계층은 모의 기준 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 AWS 모의 테이블과 키움 모의 API로 단타 저장 및 일일 총자산 스냅샷을 통합검증
- 사용자에게 확인받을 사항: 없음
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:25 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 대시보드에서 매매를 진행하거나 진행하지 않은 이유 확인
- 완료한 작업:
  - 최근 실행 이력에 `매매 이유` 열 추가
  - 결정의 `reason_codes`와 선택 후보의 기술적 근거를 함께 추출
  - 종가배팅·단타·중기·익절·손절·예약청산 주요 코드를 한글 설명으로 변환
  - 이유는 최대 5개까지 태그로 표시하고 없는 이유는 추정하지 않고 `기록 없음` 처리
  - 샘플 매수·NO_TRADE·09:10 청산에 이유 데이터 추가
  - 로컬 UI 서버를 변경 코드로 재시작
- 변경 파일:
  - `stock-automation/src/stock_automation/dashboard.py`
  - `stock-automation/src/stock_automation/dashboard_static/index.html`
  - `stock-automation/src/stock_automation/dashboard_static/app.js`
  - `stock-automation/src/stock_automation/dashboard_static/styles.css`
  - `stock-automation/examples/dashboard_fixture.json`
  - `stock-automation/tests/test_dashboard.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 결정 이유와 선택 후보 이유 병합, 모의 전용 내부 코드 제외, 한글 변환 검증
- 전체 테스트 결과: `124개 통과`
- 수동 검증 결과: Python compileall, JavaScript 문법검사, fixture JSON 검사, API에서 BUY·NO_TRADE·청산 이유 확인, `git diff --check` 통과
- 실패·미확인 사항: 과거 이벤트에 `reason_codes`가 없으면 이유를 복원하지 않음
- 남은 위험: 실제 AWS 이벤트 저장 시 모든 진입·청산 경로가 이유 코드를 빠뜨리지 않는지 통합검증 필요
- 실거래 상태: `비활성화 / 읽기 전용 UI / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C AWS 모의 통합검증에서 실제 DynamoDB 이벤트의 매매 이유 표시 확인
- 사용자에게 확인받을 사항: 이유 태그 수와 문구가 모바일에서 읽기 편한지 확인
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:22 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 대시보드에서 날짜별 총금액 변화 추이를 간단한 그래프로 확인
- 완료한 작업:
  - 하루 한 점의 총자산을 표시하는 반응형 선그래프 추가
  - 최신 총금액과 조회기간 증감액 표시
  - 모의와 실거래 그래프 전환 버튼 추가, 두 이력은 합산하지 않음
  - DynamoDB `EQUITY#<PAPER|LIVE>#<날짜>` 항목을 날짜순으로 읽는 데이터 계약 추가
  - 샘플 모의 총자산 7일 이력 추가
  - 기존 로컬 UI 서버를 새 코드로 재시작
- 변경 파일:
  - `stock-automation/src/stock_automation/dashboard.py`
  - `stock-automation/src/stock_automation/dashboard_static/index.html`
  - `stock-automation/src/stock_automation/dashboard_static/app.js`
  - `stock-automation/src/stock_automation/dashboard_static/styles.css`
  - `stock-automation/examples/dashboard_fixture.json`
  - `stock-automation/tests/test_dashboard.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 일별 자산 이력 날짜 정렬과 PAPER/LIVE 분리 검증
- 전체 테스트 결과: `123개 통과`
- 수동 검증 결과: Python compileall, JavaScript 문법검사, fixture JSON 검사, API에서 PAPER 7일 이력 확인, `git diff --check` 통과
- 실패·미확인 사항: AWS 운영 원장에서 일별 평가금액을 자동 집계해 `EQUITY#` 항목을 생성하는 작업은 아직 미구현
- 남은 위험: 실제 총자산 그래프는 보유종목의 검증된 현재가로 평가금액을 계산하는 일별 집계가 연결돼야 정확함
- 실거래 상태: `비활성화 / 읽기 전용 UI / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 UI를 확인한 뒤 AWS 모의작업 종료 시 일별 총자산 스냅샷 저장을 추가
- 사용자에게 확인받을 사항: 그래프의 색상·위치·표시기간을 보고 원하는 UI 조정 여부 확인
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:19 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 추후 UI에서 전략별로 모의매매와 실거래를 배타적 선택이 아닌 동시 선택 가능하게 준비
- 완료한 작업:
  - 종가배팅·중기·단타별로 `모의`와 `실거래`를 독립 체크하는 UI 추가
  - 두 항목이 동시에 선택된 설정을 그대로 표현하는 대시보드 데이터 모델 추가
  - 향후 DynamoDB 키 `CONTROL#STRATEGY_MODE#<전략>`에서 선택 상태를 읽는 형식 추가
  - 인증과 키움 통합검증 전에는 모든 변경 컨트롤과 실거래 효력을 잠금
  - 모의·실거래 동시 실행 시 원장·자금·포지션·성과를 분리한다는 운영 원칙 문서화
- 변경 파일:
  - `stock-automation/src/stock_automation/dashboard.py`
  - `stock-automation/src/stock_automation/dashboard_static/index.html`
  - `stock-automation/src/stock_automation/dashboard_static/app.js`
  - `stock-automation/src/stock_automation/dashboard_static/styles.css`
  - `stock-automation/tests/test_dashboard.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 모의·실거래 동시 선택이 배타적으로 변환되지 않고 보존되며 실거래 효력은 잠기는지 검증
- 전체 테스트 결과: `122개 통과`
- 수동 검증 결과: Python compileall, JavaScript 문법검사, fixture JSON 검사, `git diff --check` 통과
- 실패·미확인 사항: UI에서 설정을 실제 저장하는 인증 API와 실행 엔진의 모드 라우팅은 아직 미구현
- 남은 위험: 인증 없는 웹 요청으로 실거래 설정을 변경할 수 없도록 Cognito·CSRF 방어·감사로그가 필요
- 실거래 상태: `비활성화 / UI 선택 변경 잠금 / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C 통합검증 후 Cognito 인증이 적용된 전략 모드 설정 API를 별도 실거래 스택에 설계
- 사용자에게 확인받을 사항: 없음(모의와 실거래의 전략별 동시 선택 요구 확정)
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:16 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 키움 실거래 안전 기능을 계속 구현하고 이전에 시작한 단타 기능도 보완
- 완료한 작업:
  - 키움 주문상태에 `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED` 추가
  - 키움 누적 체결수량에서 이전 반영량을 뺀 증가분만 프로그램 포지션에 반영
  - 주문 상태와 프로그램 보유수량을 DynamoDB 트랜잭션으로 함께 변경
  - 동일 체결 조회 반복과 동시 실행 시 수량 중복 증가 방지
  - 프로그램 보유수량보다 많은 매도 및 보호 기준선을 침범하는 매도 차단
  - 키움 총보유수량은 원장 대사, 주문가능수량은 실제 매도 한도로 분리
  - 주문번호 미조회 시 비상정지를 켜고 수동 대사를 요구하는 `live-reconcile` 추가
  - 키움 KRX 읽기 API에서 단타 전용 스냅샷을 만드는 변환기 추가
  - 5분봉 20이평 재돌파와 최근 15분 수익률 계산 추가
  - 당일 검증 촉매 종목만 조회하는 `daytrade-kiwoom-scan` 단발 모의 명령 추가
  - 대시보드에서 단타 지갑·포지션·이벤트·단발 실행표를 별도 표시
  - 토스 연동은 추가하지 않았으며 키움증권만 사용
- 변경 파일:
  - `stock-automation/src/stock_automation/live_execution.py`
  - `stock-automation/src/stock_automation/live_broker.py`
  - `stock-automation/src/stock_automation/live_cli.py`
  - `stock-automation/src/stock_automation/order_safety.py`
  - `stock-automation/src/stock_automation/providers/kiwoom.py`
  - `stock-automation/src/stock_automation/indicators.py`
  - `stock-automation/src/stock_automation/models.py`
  - `stock-automation/src/stock_automation/cli.py`
  - `stock-automation/src/stock_automation/dashboard.py`
  - `stock-automation/examples/dashboard_fixture.json`
  - `stock-automation/README.md`
  - 관련 테스트 4개
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 체결 증가분 멱등 반영, 키움 단타 스냅샷, 시장지수 조회, 단타 UI 분리, 총보유·주문가능수량 분리
- 전체 테스트 결과: `121개 통과`
- 수동 검증 결과: Python compileall, JavaScript 문법검사, 대시보드 fixture JSON 검사, 새 CLI 2개 등록, `git diff --check` 통과
- 실패·미확인 사항: 키움 실제 모의 API와 AWS DynamoDB 트랜잭션은 PC-C에서 통합검증 필요, 단타 결과는 아직 로컬 JSONL이며 AWS 대시보드에 자동 저장되지 않음
- 남은 위험: 미체결 주문 자동 취소, 재시작 복구, 주기적 체결 대사, 불일치 자동 비상정지의 PC-C 통합 흐름이 남음
- 실거래 상태: `비활성화 / 비상정지 기본 ON / 실제 주문 없음 / UI 전환 불가`
- 다음 Codex의 첫 작업: PC-C에서 121개 테스트를 재실행한 뒤 키움 모의 주문 응답과 DynamoDB Local로 부분체결 원장을 통합검증
- 사용자에게 확인받을 사항: 없음(단타는 단발 모의운용, 토스 미연동으로 유지)
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 14:10 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: 이전 프로그램 제작을 계속하고 자동매매 증권사를 키움증권으로 한정
- 완료한 작업:
  - 토스 계좌·보유종목을 프로그램 범위에서 제외하고 키움 REST 계좌만 사용하도록 기준 확정
  - 계좌번호 원문을 저장하지 않는 SHA-256 계좌 지문 검증 추가
  - 키움 기존 보유종목 수량을 한 번만 기록하고 덮어쓰지 못하는 보호 기준선 추가
  - 보호 기준선은 비상정지 ON 상태와 명시적 확인 문구가 있어야 생성되도록 제한
  - 매도 가능 수량을 프로그램 확인 체결수량과 보호 기준선 초과수량 중 작은 값으로 제한
  - 계좌 지문·잔고 대사가 없으면 주문 승인을 실패 처리
  - 아직 체결 전용 원장이 없으므로 `holdings_reconciled=False`로 고정해 모든 실주문을 계속 차단
- 변경 파일:
  - `stock-automation/src/stock_automation/order_safety.py`
  - `stock-automation/src/stock_automation/live_execution.py`
  - `stock-automation/src/stock_automation/live_broker.py`
  - `stock-automation/src/stock_automation/live_cli.py`
  - `stock-automation/src/stock_automation/cli.py`
  - `stock-automation/tests/test_order_safety.py`
  - `stock-automation/tests/test_live_execution.py`
  - `stock-automation/tests/test_live_broker.py`
  - `stock-automation/README.md`
  - `Codex_세션간_공동_인수인계.md`
- 추가·변경 테스트: 계좌 지문 불일치 차단, 잔고 미대사 차단, 프로그램 수량 외 매도 차단, 보호 기준선 1회 저장·복원, 키움 보유종목 조회
- 전체 테스트 결과: `118개 통과`
- 수동 검증 결과: `python3 -m compileall -q src tests`, `git diff --check` 통과
- 실패·미확인 사항: 키움 실제 모의 API·AWS에서는 미검증, 체결수량 전용 원장과 부분체결 상태 머신은 미구현
- 남은 위험: 체결 원장이 연결되기 전에는 실주문을 안전하게 허용할 수 없으며 현재 코드도 이를 강제로 차단함
- 실거래 상태: `비활성화 / 비상정지 ON / 실제 주문 없음 / 잔고대사 잠금 ON`
- 다음 Codex의 첫 작업: 키움 주문번호별 부분체결·취소·거부 상태 머신과 프로그램 체결수량 전용 원장을 구현
- 사용자에게 확인받을 사항: 없음(토스 미연동, 키움 전용으로 확정)
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 11:20 KST — PC-D → PC-C

- 작업 PC alias: `PC-D`
- 작업 경로: `D:/Test`
- 요청 목표: D 드라이브가 없는 타 PC의 C 드라이브 경로 반영과 PC별 세션 식별 alias 추가
- 완료한 작업:
  - 현재 PC를 `PC-D`, 타 PC를 `PC-C`로 고정
  - PC-D `D:/Test`, PC-C `C:/Test` 워크스페이스 경로 기록
  - 세션 작성 양식에 작업 PC alias와 실제 작업 경로 필드 추가
  - 공통 경로 안내를 `<WORKSPACE>` 기준으로 변경
  - 타 PC 실행 가이드의 모든 `D:\Test` 경로를 `C:\Test`로 정정
- 변경 파일:
  - `Codex_세션간_공동_인수인계.md`
  - `다른_PC_프로그램_실행방법.md`
- 추가·변경 테스트: 없음(문서 변경)
- 전체 테스트 결과: 미실행(코드 변경 없음)
- 수동 검증 결과: Markdown 차이 공백 검사 통과
- 실패·미확인 사항: PC-C의 실제 폴더가 `C:/Test`가 맞는지 첫 세션에서 확인 필요
- 남은 위험: PC-C의 실제 경로가 다르면 alias는 유지하고 경로만 정정해야 함
- 실거래 상태: `비활성화 / 비상정지 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: PC-C에서 `C:/Test/stock-automation`의 실제 존재를 확인하고 alias `PC-C`로 세션 기록
- 사용자에게 확인받을 사항: PC-C 실제 프로젝트 경로가 다를 경우에만 정정 경로 확인
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 11:18 KST — 현재 PC Codex → 다른 PC Codex

- 요청 목표: 종가배팅 점수 보완과 세 번째 전략인 장중 단타의 설계·기본 모의엔진 추가
- 완료한 작업:
  - 코스피·코스닥 종목별 시장 약세 감점과 -3% 신규진입 차단
  - 키움 `ka90009` 기관 수급과 `ka90004` 프로그램 수급 연동
  - 외국인 수급 미사용, 수급 API 실패 시 추정 없이 확인 불가 처리
  - 종가배팅 규칙 버전을 `closing-v0.2`로 갱신
  - 전용 `DAY_TRADE` 모델·점수·포지션·청산 엔진 추가
  - 단타 진입시간 09:10~14:50, 15:10 의무 당일청산, 자금 25%, 계획손실 8천원
  - 단타용 `daytrade-analyze` CLI와 별도 JSONL 원장 경로 추가
  - 종가배팅·중기·단타가 규칙, 자금, 포지션, 원장을 공유하지 않도록 분리
- 변경 파일:
  - `stock-automation/src/stock_automation/config.py`
  - `stock-automation/src/stock_automation/models.py`
  - `stock-automation/src/stock_automation/engine.py`
  - `stock-automation/src/stock_automation/providers/kiwoom.py`
  - `stock-automation/src/stock_automation/day_trade.py`
  - `stock-automation/src/stock_automation/day_trade_io.py`
  - `stock-automation/src/stock_automation/cli.py`
  - `stock-automation/src/stock_automation/reporting.py`
  - `stock-automation/README.md`
  - `stock-automation/tests/test_engine.py`
  - `stock-automation/tests/test_kiwoom_provider.py`
  - `stock-automation/tests/test_kiwoom_spec_contract.py`
  - `stock-automation/tests/test_day_trade.py`
- 추가·변경 테스트: 시장별 급락, 시장 약세 감점, 수급 API 정규화·실패, 단타 진입·NXT 제외·시장 급락·시간창·손절·당일 청산
- 전체 테스트 결과: `114개 통과`
- 수동 검증 결과: `daytrade-analyze --help` CLI 등록 확인, `git diff --check` 통과
- 실패·미확인 사항: 키움 실제 모의 API 통합, AWS 배포, 모바일 대시보드의 단타 화면은 미실행
- 남은 위험: 단타 입력 스냅샷 자동수집과 AWS 반복 스케줄러가 아직 없으며, 기본 엔진은 상시감시가 아님
- 실거래 상태: `비활성화 / 비상정지 ON / 실제 주문 없음`
- 다음 Codex의 첫 작업: Git 변경을 확인한 뒤 다른 PC에서 114개 전체 테스트를 재실행하고 키움 모의 스냅샷 수집 연결을 설계
- 사용자에게 확인받을 사항: 단타 AWS 스캔 주기와 단타 전용 모의자금
- 전달 파일 버전 또는 복사시각: Git 커밋·push 전 로컬 변경 상태

### 2026-10-12 — 회사 PC Codex → 집 PC Codex

- 요청 목표: 모의매매 프로그램 점검·수정, 전문형 운영 UI, AWS 및 실거래 후속 준비
- 완료한 작업:
  - 종가배팅 점수 0~100 정규화
  - 검증되지 않은 촉매 매수 차단
  - 비상 손절 기준 포지션 수량 계산
  - AWS 5분봉 확인 손절 연결
  - 09:10 잔여 수량 청산 우선
  - 1차 부분익절 반복 방지
  - 당일 5분봉만 사용한 VWAP
  - 주문 승인과 주문내용 해시 결합
  - `SABU Trading Console` 읽기 전용 UI 추가
  - PC·모바일 UI 렌더링 확인
  - 사용자 준비 가이드와 실거래 후속 프롬프트 작성
- 주요 변경 파일:
  - `src/stock_automation/engine.py`
  - `src/stock_automation/risk.py`
  - `src/stock_automation/exit_engine.py`
  - `src/stock_automation/aws_runtime.py`
  - `src/stock_automation/providers/kiwoom.py`
  - `src/stock_automation/order_safety.py`
  - `src/stock_automation/live_execution.py`
  - `src/stock_automation/live_broker.py`
  - `src/stock_automation/dashboard.py`
  - `src/stock_automation/dashboard_static/`
  - `src/stock_automation/cli.py`
  - `README.md`
  - 관련 테스트 파일
- 전체 테스트 결과: 105개 통과
- 수동 검증 결과: CLI 모의분석, API 응답, PC·모바일 대시보드 확인
- 실패·미확인 사항: AWS 실제 모의배포와 키움 모의 API 통합검사는 아직 수행하지 않음
- 남은 위험: 기존 보유종목 보호와 실체결 원장이 없어 실거래 불가
- 실거래 상태: `비활성화 / UI 안전조건 미충족 / 실제 주문 없음`
- 다음 Codex의 첫 작업: 실제 파일과 105개 테스트를 확인한 뒤 실거래 후속 프롬프트의
  계좌 고정·기존 보유종목 보호부터 구현
- 사용자에게 확인받을 사항: 자동매매 전용 키움 계좌 사용 가능 여부
- 전달 파일 버전 또는 복사시각: 집 PC로 복사한 실제 시각을 사용자가 기록

### 2026-10-12 — 실행환경 역할 확정

- 결정: 현재 PC에서는 프로그램을 주로 실행하지 않고 다른 PC를 기본 실행환경으로 사용
- 현재 PC 역할: 코드·문서·검토·인수인계
- 다른 PC 역할: 테스트·Docker·키움 모의연결·AWS 실행
- 검증 원칙: 실행 완료 주장은 다른 PC의 실제 출력이 있을 때만 확정
- 실거래 상태: `비활성화 / 실제 주문 없음`
- 다음 Codex의 첫 작업: 다른 PC에서 폴더 구조 확인 후 전체 테스트 실행

## 11. 다른 PC에서 이 PC로 돌아올 때 사용할 프롬프트

```text
첨부한 Codex 세션 간 공동 인수인계에서 가장 최신 전달 기록을 먼저 읽어줘.
너의 PC alias를 `PC-C`로 기록하고, 그 기록에 적힌 변경 내용을
C:/Test/stock-automation 코드와 테스트로 재검증해줘.
다른 PC에서 수정한 파일을 임의로 되돌리지 말고, 충돌이나 미완성 변경이 있으면 먼저
보고해줘. 실제 주문과 실계좌 연결은 계속 비활성화한 상태로 작업을 이어가줘.
작업이 끝나면 같은 문서의 세션 전달 기록 맨 위에 이번 결과를 추가해줘.
```

## 12. 이 PC에서 다른 PC로 보낼 때 사용할 프롬프트

```text
이 프로젝트는 두 PC의 Codex가 번갈아 작업한다. 첨부한 공동 인수인계 문서의 최신
기록과 AGENTS.md를 먼저 읽고 실제 코드로 확인해줘. 기존 변경을 보존하고, 이번
세션에서 수정한 파일·테스트·미완성 위험을 작업 종료 전에 공동 인수인계에 추가해줘.
이 PC의 alias는 `PC-C`, 기본 워크스페이스는 `C:/Test`로 기록해줘.
실계좌 주문은 실행하지 말고 실거래 안전 기능의 코드와 테스트만 진행해줘.
```

## 13. 충돌 처리 규칙

두 PC에서 같은 파일을 각각 수정했다면 한쪽 파일로 덮어쓰지 않는다.

1. 두 복사본의 수정시각과 변경내용을 확인한다.
2. 각각 별도 백업한다.
3. 차이를 비교한다.
4. 안전 관련 변경은 이유를 확인한 뒤 병합한다.
5. 병합 후 전체 테스트를 실행한다.
6. 충돌과 선택한 해결방법을 전달 기록에 남긴다.

테스트가 통과한다는 이유만으로 다른 PC의 안전장치를 삭제하지 않는다.

## 14. 실거래 관련 최종 상태 표현

실거래 준비를 보고할 때는 다음 다섯 항목을 항상 분리한다.

```text
LIVE CODE SAFETY: 미완성/완성
LIVE TESTS: 미실행/통과/실패
LIVE AWS DEPLOYMENT: 미배포/배포
LIVE ORDER SUBMISSION: 없음/있음
KILL SWITCH: ON/OFF
```

`코드 완성`과 `실거래 활성화`를 같은 의미로 사용하지 않는다.
