# PC-C 단독 진행용 전체 인수인계

> 목적: PC-D 또는 이전 Codex와 더 이상 대화할 수 없어도 PC-C에서 프로젝트를
> 안전하게 실행·검증·개발할 수 있도록 현재 상태와 다음 절차를 한 파일에 정리한다.
>
> PC-C 기준 워크스페이스: `C:/Test`
>
> 작성 기준일: 2026-10-12 KST

## 0. 새 Codex에게 처음 보낼 프롬프트

PC-C에서 새 Codex 세션을 시작할 때 아래 내용을 그대로 전달한다.

```text
이 PC의 alias는 PC-C이고 워크스페이스는 C:/Test야.
C:/Test/AGENTS.md와 C:/Test/PC-C_단독진행_전체인수인계.md,
C:/Test/Codex_세션간_공동_인수인계.md,
C:/Test/stock-automation/README.md를 먼저 끝까지 확인해줘.

문서만 믿지 말고 실제 Git 상태와 코드, 전체 테스트로 현재 상태를 재검증해줘.
기존 변경을 임의로 되돌리지 말고 충돌이 있으면 두 변경을 비교해서 안전하게 병합해줘.

현재 기본 범위는 키움증권 모의투자와 AWS 모의운용이야. 토스는 연동하지 않고,
NXT 대상 종목은 추천 대상에서 제외하며 NXT 예약은 꺼둬.
LIVE_ORDER_ENABLED=1 설정, 비상정지 해제, 실제 주문, 실계좌 Secret 연결은 하지 마.

먼저 전체 테스트와 읽기 전용 온라인 진단을 실행하고 결과를 알려줘.
그다음 이 문서의 'PC-C에서 바로 진행할 순서'를 따라 미완성 작업을 이어가줘.
모든 코드·문서 작업 후에는 Codex_세션간_공동_인수인계.md의 최신 기록 위에
PC-C 작업 결과, 변경 파일, 테스트, 미확인 사항, 실거래 상태를 추가해줘.
비밀키·토큰·계좌번호는 대화, 코드, Markdown, Git, 로그에 출력하지 마.
```

## 1. 절대 안전 규칙

현재 허용되는 작업:

- 코드 분석·수정과 전체 테스트
- 가짜 응답 및 키움 모의투자 API 검증
- 모의전략의 AWS 배포·DynamoDB·S3·CloudWatch 검증
- 읽기 전용 모바일 대시보드 확인
- 실거래 안전 기능의 코드와 테스트 작성

현재 금지되는 작업:

- 실제 계좌 주문 제출
- `LIVE_ORDER_ENABLED=1` 설정
- 비상정지 해제
- 실제 계좌 App Key·Secret 연결
- UI에서 실거래 모드를 유효화
- 사용자의 별도 승인 없는 유료 인프라 추가
- NAT Gateway, RDS, 로드밸런서 등 고정비 인프라의 임의 생성

비밀정보는 다음 어디에도 기록하지 않는다.

- Codex·웹 GPT 대화
- Markdown과 소스 코드
- Git 커밋과 이슈
- PowerShell 스크립트와 명령 기록
- CloudWatch 일반 로그

대상 비밀정보에는 키움 키, AWS 키·토큰, 계좌번호·비밀번호, 텔레그램 토큰과
`chat_id`, OpenDART 키가 포함된다. AWS에서는 Secrets Manager를 사용한다.

## 2. 프로젝트의 최종 목적과 현재 범위

최종 목적은 키움증권과 연동한 안전한 자동매매지만 현재 제품 단계는
**분석·모의매매 우선**이다.

전략 우선순위:

1. 종가배팅: KRX 15:20 모의진입, 다음 거래일 09:10 기본 청산
2. 중기: 수 주에서 1~2개월 보유하는 별도 전략
3. 단타: 사용자 요청 시 한 번만 실행하는 모의 단발 스캔

공통 원칙:

- 종가배팅·중기·단타의 자금, 포지션, 점수, 원장, 성과를 섞지 않는다.
- 추천할 종목이 없으면 `NO_TRADE`가 정상 결과다.
- 토스는 분석 화면 참고용일 뿐 자동매매에는 연결하지 않는다.
- 증권사 연결은 키움증권만 사용한다.
- NXT 거래 가능 종목은 최종 추천에서 제외한다.
- 단타를 AWS에서 상시 감시하거나 반복 실행하지 않는다.

## 3. 기준 파일과 우선순위

새 세션은 다음 순서로 확인한다.

1. `C:/Test/AGENTS.md`
2. `C:/Test/PC-C_단독진행_전체인수인계.md`
3. `C:/Test/Codex_세션간_공동_인수인계.md`
4. `C:/Test/stock-automation/README.md`
5. `C:/Test/다른_PC_프로그램_실행방법.md`
6. `C:/Test/AWS_자동매매_실행가이드.md`
7. `C:/Test/실거래_개발_후속_Codex_프롬프트.md`
8. `C:/Test/docs/프로그램 설계/`

문서가 충돌하면 `AGENTS.md`, 실제 코드, 현재 테스트 결과 순서로 판단하고 충돌을
새 인수인계 기록에 남긴다.

## 4. PC-C 폴더 구조

```text
C:/Test/
├─ AGENTS.md
├─ PC-C_단독진행_전체인수인계.md
├─ Codex_세션간_공동_인수인계.md
├─ 다른_PC_프로그램_실행방법.md
├─ AWS_자동매매_실행가이드.md
├─ stock-automation/
├─ Kiwoom-REST-API/
└─ docs/
```

`stock-automation`과 `Kiwoom-REST-API`는 반드시 형제 폴더로 둔다. Docker 빌드
컨텍스트는 `C:/Test`이고 Dockerfile은 `stock-automation/Dockerfile`이다.

## 5. 현재 구현 상태

2026-10-12 PC-D에서 확인된 상태이며 PC-C에서 다시 검증해야 한다.

구현된 주요 기능:

- 종가배팅 0~100점 평가와 검증 촉매 필수 조건
- KRX 14:50 스캔, 15:10 후보 축소, 15:20 모의결정
- 다음 거래일 09:05 검토와 09:10 잔여수량 청산
- 5분봉 확인 손절과 별도 비상 하드 스톱
- 기관·프로그램 수급 사용, 실시간 외국인 수급 미사용
- 중기전략 신호·진입·재검토와 전용 지갑
- 단타 전용 모델·점수·지갑·포지션
- 단타 `DAY_TRADE_ON_DEMAND` 단발 AWS 실행
- DynamoDB 원자적 지갑 차감과 중복 결정 방지
- S3 원본 스냅샷·결정 저장
- 15:50 일일 총자산 스냅샷
- 텔레그램 알림 outbox
- PC·모바일용 읽기 전용 `SABU Trading Console`
- 실주문 의도 생성·사용자 승인·계좌 기준선·부분체결 원장 골격
- 비상정지 기본 ON과 실거래 UI 잠금

마지막 로컬 검증:

```text
전체 단위 테스트: 140개 통과
Python compileall: 통과
CloudFormation YAML 구문 로드: 통과
실제 AWS·키움 모의 통합검증: 미실행
실제 주문: 없음
```

PC-C에서 140개보다 테스트 수가 적으면 파일 누락이나 브랜치 차이를 먼저 확인한다.

## 6. 데이터 저장 구조

현재는 PostgreSQL을 사용하지 않고 DynamoDB 온디맨드를 사용한다.

주요 키 예시:

```text
WALLET#CLOSING_BET#KRX_1520
WALLET#MEDIUM_TERM
WALLET#DAY_TRADE
OPEN#CLOSING_BET#KRX_1520
OPEN#MEDIUM_TERM
OPEN#DAY_TRADE
DAY#...
EQUITY#PAPER#YYYY-MM-DD
LIVE_ORDER#<intent-id>
PROGRAM_POSITION#<stock-code>
CONTROL#ACCOUNT_GUARD
CONTROL#STRATEGY_MODE#<strategy>
```

DynamoDB는 주문 상태, 지갑, 열린 포지션, 중복 방지, 비상정지와 일일 총자산에
적합하다. PostgreSQL은 대량의 1분봉·5분봉을 장기 저장하거나 수백만 건의 복잡한
백테스트·SQL 분석이 필요해질 때 분석 전용으로 검토한다. 단타가 존재한다는 이유만으로
지금 PostgreSQL이나 RDS를 추가하지 않는다.

## 7. PC-C에서 바로 진행할 순서

### 7.1 Git과 파일 상태 확인

```powershell
Set-Location C:\Test
git status --short
git branch --show-current
git log -5 --oneline
```

사용자 변경과 다른 PC 변경을 임의로 되돌리지 않는다. 충돌 파일은 양쪽을 백업하고
차이를 비교한 뒤 병합한다.

### 7.2 Python 전체 테스트

```powershell
Set-Location C:\Test\stock-automation
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

하나라도 실패하면 Docker 배포와 AWS 예약 활성화를 중단한다.

### 7.3 Docker 빌드

```powershell
Set-Location C:\Test
docker build -f stock-automation\Dockerfile -t stock-automation:dev .
docker image inspect stock-automation:dev
```

### 7.4 키움 모의 읽기 점검

키움 공식 설정으로 모의투자 키를 등록한 뒤 실행한다.

```powershell
$env:KIWOOM_MODE = "demo"
$env:KIWOOM_TOKEN_STORE = "memory"
stock-automation doctor --online
```

이 단계는 주문을 제출하지 않는다.

### 7.5 AWS 최초 배포

정확한 명령과 Secret 형식은 `C:/Test/다른_PC_프로그램_실행방법.md`의 8절을
따른다. 최초 배포는 반드시 다음 상태여야 한다.

```text
CoreScheduleState=DISABLED
NxtScheduleState=DISABLED
KIWOOM_MODE=demo
LIVE_ORDER_ENABLED 미설정
```

AWS 온라인 진단 결과가 `ok: true`인 경우에만 핵심 모의예약 활성화를 검토한다.

### 7.6 단타 단발 실행

단타는 자동 스케줄이 아니다. 당일 출처·검증시각이 있는 촉매 파일을 S3에 올리고
KST 09:10~14:50 사이에 사용자가 요청한 경우에만 ECS 환경변수를 다음과 같이
덮어써서 한 번 실행한다.

```text
RUN_PHASE=DAY_TRADE_ON_DEMAND
```

반복 스케줄이나 항상 켜진 컨테이너를 만들지 않는다. 자세한 `aws ecs run-task`
명령은 다른 PC 실행방법의 8.8절을 사용한다.

### 7.7 일일 총자산 확인

핵심 모의예약을 활성화하면 거래일 15:50에 다음 단계가 실행된다.

```text
RUN_PHASE=EQUITY_SNAPSHOT_1550
```

모든 모의전략 지갑의 가용현금과 열린 포지션의 검증 현재가 평가액을 합산한다.
현재가가 없거나 오래됐으면 해당 날짜 스냅샷을 만들지 않는 것이 정상이다.

## 8. AWS 예약표

| KST | 단계 | 설명 |
|---|---|---|
| 09:05 | `EXIT_0905` | 종가배팅 손절·목표 검토 |
| 09:10 | `EXIT_0910` | 종가배팅 잔여수량 청산 |
| 09:15 | `MEDIUM_ENTRY_0915` | 중기 신호 진입 확인 |
| 14:50 | `SCAN_1450` | 종가배팅 전체 스캔 |
| 15:10 | `SHORTLIST_1510` | 후보 축소 |
| 15:20 | `ENTRY_1520` | 종가배팅 모의진입 또는 NO_TRADE |
| 15:35 | `MEDIUM_REVIEW_1535` | 중기 보유 재검토 |
| 15:40 | `MEDIUM_SIGNAL_1540` | 중기 신규 신호 |
| 15:50 | `EQUITY_SNAPSHOT_1550` | 일일 총자산 기록 |
| 토 08:00 | `TUNE_WEEKLY` | 모의전략 기록 기반 검증 |

`DAY_TRADE_ON_DEMAND`는 표의 예약에 포함하지 않는다. NXT 예약은 계속 비활성화한다.

## 9. 5거래일 모의운용

모의운용 시작일부터 거래일 기준 5일간 매일 확인한다.

- 예약 작업 성공·실패와 실제 실행 시각
- `BUY`, `SELL`, `NO_TRADE` 및 판단 이유
- 모의 진입·청산 가격과 수량
- 전략별 지갑과 포지션 일치
- 동일 이벤트·동일 포지션 중복 생성 여부
- 일일 총자산과 전일 대비 변화
- 오래된 시세, API 제한, 재시도, 알림 실패
- 실주문 없음과 비상정지 기본 ON

원본은 Git에서 제외된 아래 폴더에 저장한다.

```text
C:/Test/stock-automation/runtime/validation/
```

Git으로 전달할 요약 보고서는 다음에 만든다.

```text
C:/Test/docs/운영 검증/YYYY-MM-DD_5거래일_모의운용_검증.md
```

보고서에는 비밀정보를 제외하고 다음을 포함한다.

- 분석 기간과 AWS 리전
- 날짜별 작업 성공표
- 종목, 결정, 모의가격·수량, 매매 이유
- 실현·미실현 모의손익과 일일 총자산
- 중복·불일치·오류·재시도
- 실거래 전환 `통과 / 추가 모의 필요 / 불가` 판정

원본 CloudWatch와 DynamoDB JSON은 Git에 올리지 않는다.

## 10. 대시보드

로컬 샘플 UI:

```powershell
Set-Location C:\Test\stock-automation
$env:PYTHONPATH = "src"
python -m stock_automation.cli dashboard --fixture examples/dashboard_fixture.json
```

브라우저에서 `http://127.0.0.1:8765`를 연다.

현재 UI는 읽기 전용이며 외부 인터넷에 직접 공개하지 않는다. 모바일 외부 접속은
Cognito 인증, HTTPS, 감사로그를 붙인 별도 배포가 끝난 뒤에만 허용한다. 단순히
포트 8765를 보안 그룹에 여는 방식은 금지한다.

UI에는 실거래 안전센터와 주문 진행 타임라인이 포함돼 있다. `PAPER_TABLE`과 별도
`LIVE_ORDER_TABLE`을 함께 지정하면 두 테이블을 읽기 전용으로 합쳐 비상정지,
보호 기준선, 최근 10분 이내 대사, 진행·불확실 주문을 표시한다. 계좌번호·별칭·지문은
응답에 포함하지 않는다. 모바일에서는 실행 이력이 카드로 표시되고 하단 빠른 메뉴가
나타난다. 실제 테이블 연결 전에는 샘플 fixture로만 확인한다.

## 11. Git과 배포 관계

현재 Git push만으로 AWS가 자동 갱신되는 CI/CD는 구현되어 있지 않다.

현재 배포 흐름:

```text
코드 수정
→ 전체 테스트
→ Git commit/push
→ PC-C에서 Docker 이미지 빌드
→ ECR push
→ CloudFormation deploy
→ 예약 비활성 상태에서 진단
→ 모의예약 활성화
```

CI/CD를 추가할 때도 실거래 배포와 예약 활성화를 자동 승인하지 않는다. 최소한 테스트,
이미지 취약점 검사, 모의 스택 배포까지만 자동화하고 실거래는 수동 승인 단계를 둔다.

## 12. 예상 AWS 비용과 금지할 고정비

현재 예약형 모의구조는 통상 월 약 3,000~8,000원, 여유 예산은 월 1만원 수준으로
예상한다. 실제 사용시간, 로그량, 환율과 무료 크레딧에 따라 달라진다.

임의로 추가하지 않을 항목:

- NAT Gateway
- 항상 켜진 ECS 서비스나 EC2
- Application Load Balancer
- RDS·Aurora PostgreSQL
- OpenSearch

위 항목은 월 고정비를 크게 늘릴 수 있으므로 필요성·대안·월 예상비용을 사용자에게
먼저 설명하고 승인받는다. AWS Budgets에 월 예산 알림을 설정한다.

## 13. 실주문은 언제 가능한가

현재는 불가능하다. 코드에 수동 `live-*` 명령 골격이 있어도 운영 준비 완료를 뜻하지
않는다.

필수 완료 조건:

1. 키움 주문·부분체결·미체결·취소의 실제 통합검증
2. 구현된 장시간 미체결 잔량 취소의 키움 실제 응답 검증
3. 구현된 재시작 안전복구의 실제 DynamoDB 검증
4. 구현된 주문·체결·잔고 1회 대사의 운영 주기 확정 및 통합검증
5. 구현된 불일치 자동 비상정지의 실제 테이블 검증
6. 계좌 지문과 기존 보유종목 보호 기준선 검증
7. 실거래 전용 DynamoDB·Secret·IAM·AWS 스택 분리
8. Cognito·HTTPS·감사로그가 적용된 모드 변경 경로
9. 5거래일 이상 모의운용 통과
10. 사용자의 별도 명시적 승인

조건을 충족해도 첫 단계는 자동 주문이 아니다. 사용자가 주문별로 승인하는 극소액
감독형 주문 1건으로 시작해 키움 주문내역, 체결 원장, 프로그램 보유수량을 대조한다.

현재 상태 표현:

```text
LIVE CODE SAFETY: 미완성
LIVE TESTS: 로컬 140개 통과 / 실제 통합검증 미실행
LIVE AWS DEPLOYMENT: 미배포
LIVE ORDER SUBMISSION: 없음
KILL SWITCH: 기본 ON 설계 / 실제 테이블 상태 확인 필요
```

## 14. 남은 개발 작업 우선순위

### PC-C에서 즉시 가능한 작업

1. 실제 파일 기준 140개 전체 테스트 재실행
2. Docker 빌드
3. 키움 모의 읽기 진단
4. AWS 스케줄 비활성 최초 배포
5. `DAY_TRADE_ON_DEMAND` 단발 통합검증
6. `EQUITY_SNAPSHOT_1550` 수동 통합검증
7. CloudWatch·S3·DynamoDB·텔레그램 일치 확인
8. 핵심 모의예약 활성화와 5거래일 운영

### 코드로 완료됐지만 PC-C 통합검증이 필요한 작업

1. 키움 `kt10003` 잔량 취소(자동 재시도 금지)
2. 기본 180초 장시간 미체결 시간 초과 처리
3. `ACKNOWLEDGED`·`PARTIALLY_FILLED` 재조회 및 모호한 상태의 안전 중지
4. 주문·누적 체결·전체 잔고 1회 대사
5. 수량·계좌 지문·주문번호 불일치 시 자동 비상정지

실행 명령은 `live-supervise`이며 한 번 실행하고 종료한다. 실제 주문·취소가 가능한
명령이므로 PC-C에서도 키움 실제 통합검증 계획과 사용자 승인이 끝나기 전에는 실행하지
않는다. 현재 AWS 예약에는 연결하지 않았다.

### 코드로 남은 작업

1. 실거래 전용 AWS 인프라 템플릿
2. Cognito 인증·HTTPS 대시보드 배포
3. 인증된 전략별 모의·실거래 모드 저장 API
4. CloudWatch 오류와 실제 스케줄 상태의 UI 표시
5. 검증 촉매 자동수집

### 지금 하지 않을 작업

- 단타 상시 모니터링
- NXT 자동매매
- PostgreSQL 도입
- UI에서 한 번의 클릭으로 실거래 활성화
- 모의전략 결정을 실제 주문에 자동 연결

## 15. 장애 발생 시

다음 중 하나라도 발생하면 핵심 스케줄을 즉시 `DISABLED`로 배포한다.

- 오래된 시세 사용
- 중복 이벤트 또는 중복 포지션
- 지갑과 포지션 금액 불일치
- 알 수 없는 주문 상태
- 키움 주문번호 미조회
- 예상하지 못한 AWS 비용 증가
- 알림 또는 거래일 달력 오류

기록은 삭제하지 않는다. S3와 DynamoDB는 원인을 확인할 때까지 보존한다. 실제 주문
응답이 불명확하면 자동 재주문하지 않는다.

## 16. 매 작업 종료 시 인수인계 형식

`C:/Test/Codex_세션간_공동_인수인계.md`의 세션 전달 기록 맨 위에 추가한다.

```text
작업 PC alias: PC-C
작업 경로: C:/Test
요청 목표:
완료한 작업:
변경 파일:
추가·변경 테스트:
전체 테스트 결과:
수동 검증 결과:
실패·미확인 사항:
남은 위험:
실거래 상태:
다음 Codex의 첫 작업:
사용자에게 확인받을 사항:
전달 파일 버전 또는 Git 커밋:
```

실거래 상태는 다음 다섯 줄을 별도로 기록한다.

```text
LIVE CODE SAFETY: 미완성/완성
LIVE TESTS: 미실행/통과/실패
LIVE AWS DEPLOYMENT: 미배포/배포
LIVE ORDER SUBMISSION: 없음/있음
KILL SWITCH: ON/OFF/미확인
```

## 17. 최종 체크리스트

- [ ] `AGENTS.md`와 이 문서를 읽음
- [ ] Git 변경과 브랜치 확인
- [ ] 기존 변경을 되돌리지 않음
- [ ] Python 전체 테스트 통과
- [ ] Docker 빌드 성공
- [ ] 키움 모의 읽기 점검 성공
- [ ] 최초 AWS 예약 `DISABLED` 확인
- [ ] NXT 예약 `DISABLED` 확인
- [ ] 실계좌 Secret 미연결 확인
- [ ] `LIVE_ORDER_ENABLED` 미설정 확인
- [ ] 비상정지 기본 ON 확인
- [ ] 단타 자동 스케줄 없음 확인
- [ ] 15:50 총자산 기록 확인
- [ ] 5거래일 검증 보고서 작성
- [ ] 비밀정보가 Git에 없는지 확인
- [ ] 공동 인수인계 최신 기록 추가
