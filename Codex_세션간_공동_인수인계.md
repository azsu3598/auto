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
10절에는 위치 기준 최근 5개 기록만 둔다. 6번째가 되는 기록은 같은 commit에서 원문 그대로
`docs/운영 검증/공동_인수인계_세션기록_보관.md`의 `보관 기록` 맨 위로 옮긴다. 이동은 저장소
루트에서 `python stock-automation/tools/handoff_archive.py rotate`로 하고 `PASSED`를 확인한다. 원문 이동은
삭제가 아니며, 어느 파일에서도 기록 내용을 수정·요약·재정렬하지 않는다.

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
이 절의 항목과 테스트 수는 이후 갱신되지 않았다. 최신 상태는 10절 최근 기록과
`PC-C_단독진행_전체인수인계.md` 상단 최신 보완 절, 실제 코드·테스트로 확인한다.

### 구현된 항목

- 종가배팅 분석·모의매매 엔진
- KRX 14:50, 15:10, 15:20 예약 단계
- 다음 거래일 09:05 점검과 09:10 잔여 수량 청산
- 프로그램의 NXT 가능 종목 KRX 종가배팅 제외 필터 유지. 단, 2026-10-20 사용자 지시로 대화상 분석·추천에는 NXT 종목도 포함하며 프로그램 설정 변경을 뜻하지 않는다.
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

새 기록을 10절 바로 아래, 가장 위에 추가한다. 추가 후 6번째가 된 기록은 보관 파일로 옮긴다.

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

최근 5개 기록만 이 절에 유지한다. 이전 기록은 원문 그대로 [보관 파일](docs/운영%20검증/공동_인수인계_세션기록_보관.md)로 옮겼다.

### 2026-10-28 PC-D / Claude → PC-C / 병행계획 A2 가짜 응답 시나리오 테스트·A4 증권사 검증 계획(코드 변경 없음)

- A2 새 테스트 `tests/test_live_scenarios.py` 15개: 실제 `KiwoomLiveBroker`·`DynamoLiveOrderStore`·`LiveOrderExecutor`·`LiveOrderSupervisor`를 묶고 키움 응답만 스크립트로 바꿨다. 주문 단계(증권사 오류 응답·주문번호 없는 응답·응답 유실·claim 직후 중단 재시작 → `UNCERTAIN`/kill switch, 재전송 없음), 체결 단계(부분체결→시간 초과 취소→취소 완료 시 체결분만 보유, 시간 전 미체결 유지, 접수 후 거부, 다음 페이지에서 주문 발견, 주문 미발견, 누적 체결 감소, 취소 수량 불일치 → 재취소 없음), 계좌 단계(부분 매도는 프로그램 수량만 감소, 프로그램 수량 초과 매도 체결 거부, 보호 보유분 수동 매도 감지, 보유 조회 실패). 외부 통신 없음.
- 테스트 보조 수정 `tests/test_live_execution.py` `FakeDdb`: 상태 결정 순서에서 `:uncertain`을 `:cancel_submitting`보다 먼저(실제 `mark_cancel_uncertain`과 같게), 체결 트랜잭션 조건에 `CANCEL_ACKNOWLEDGED` 허용(실제 `reconcile_fill` 조건과 같게). 기존 13개 그대로 통과.
- 발견(정책 확인 필요, 코드 미수정): 증권사의 명확한 주문 거절(`return_code`≠0, 예: 주문가능금액 부족)도 `UNCERTAIN`으로 잠겨 수동 대사 전까지 거래가 멈춘다. 안전 쪽 동작이며, 실제 거절 응답 형식을 A4 R1b에서 확인한 뒤 판단한다.
- A4 새 문서 `docs/운영 검증/2026-10-28_실거래_증권사검증계획.md`: 실계좌로만 확인 가능한 V1~V10(가장 위험: `kt00007` `acpt_tp` 거부·취소 문구), 단계 R0 읽기만 → R1 미체결 1주 주문·취소 → R1b 거절 주문 → R2 1주 체결 매수 → R3 매도(10:00~14:00, KRX, 저가 1주), 시험 시간만 `LIVE_ORDER_ENABLED=1` 허용하는 별도 검토 템플릿 권장, 중단 조건, 증거 기록 범위(비밀값 없음), 주문 4건+취소 1건 상한.
- 검증(PC-D): 새 15개 OK. 전체 416개 실행, 실패 9건(아래 기록들과 같은 `botocore`·`truststore` 환경 요인), 새 실패 없음. `compileall` 통과, `git diff --check` 통과.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 변경 없음, 실제 주문 없음. commit 없음, push 없음.

### 2026-10-28 PC-D / Claude → PC-C / 병행계획 A3: 잠긴 실거래 전용 템플릿 작성(배포 없음)

- 새 템플릿 `stock-automation/infra/live-locked.yaml`(JSON 형식): 실거래 전용 DynamoDB `stock-automation-live`(삭제 보호·PITR·Retain), ECS 클러스터·작업 정의 `stock-automation-live`(기본 명령 `--help`, 비루트·읽기 전용·권한 제거), 로그 `/stock-automation/live`(365일), 실행/작업 역할. 예약·규칙·Lambda·EC2·서비스 없음.
- 잠금: `LiveOrderEnabled` 허용값 `"0"`만(→ `live-execute`·`live-supervise` 실행 불가). kill switch 기록을 만들지 않아 기본 ON. 한도 파라미터 기본값=최대값(30만/60만/1만/2종목/종목당 하루 1회). `KiwoomRealSecretArn` 기본 빈 값이면 키·Secret 읽기 권한 없음(연결은 별도 승인 갱신). 작업 역할은 실거래 테이블만, `DeleteItem`은 `CONTROL#LIVE_EXECUTION_LOCK`만, 모의 테이블·버킷 명시 Deny.
- 새 테스트 `tests/test_live_infrastructure.py` 8개. `tools/validate_paper_infrastructure.py` `TEMPLATE_NAMES`에 추가(`test_paper_batch_checks`가 `infra/*.yaml` 전체 등재를 요구).
- 새 문서 `docs/운영 검증/2026-10-28_실거래_잠금템플릿_운영안내.md`: 리소스·잠금·Secret JSON 키(값 없음)·지문 로컬 계산·단계(배포 → Secret 연결 → 기준선 잠금, 각각 별도 승인)·이상 시 대응·미확인.
- 검증(PC-D): 새 8개 OK. 전체 401개 실행, 실패 9건(아래 기록과 같은 `botocore`·`truststore` 환경 요인), 새 실패 없음. `compileall` 통과, `git diff --check` 통과. **`cfn-lint` 미설치로 스키마 검사 미실행** — PC-C에서 `validate_paper_infrastructure.py` 실행 필요.
- 남은 위험·미확인: 키움 실계좌 허용 IP 등록 요구 여부, 실제 `ka00001`·`kt00018` 응답. 역할에 Permission Boundary가 없어 관리자 배포가 전제다. 한도 상향은 A5 결정 후 템플릿 수정 필요.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 변경 없음, 배포 없음, 실제 주문 없음. commit 없음, push 없음.

### 2026-10-28 PC-D / Claude → PC-C / A1 발견 ①~⑥ 실거래 안전 수정(실거래 경로만)

- 사용자 요청: 일정 단축을 위해 아래 A1 기록의 ①~⑥을 수정. ⑦(일 손실한도 범위)·⑧(미체결 자동 취소)은 A5 실계좌 조건과 함께 결정하므로 손대지 않았다.
- `live_broker.py`: 계좌 조회 연속 페이지 전체 읽기(`_pages`, 20페이지 초과 시 실패), `kt00018`·`kt00007`에 적용. `account_numbers()`(`ka00001` `acctNo`, 숫자만 정규화). `account_risk_state(program_positions=...)`를 주면 노출·보유종목 수를 프로그램 보유분만으로 계산(없으면 기존처럼 계좌 전체).
- `order_safety.py`: `LiveOrderPolicy.maximum_daily_buy_orders_per_code`(기본 1) → `DAILY_CODE_ORDER_LIMIT`, `AccountRiskState.ambiguous_orders` → `AMBIGUOUS_ORDER_STATE`.
- `live_execution.py`: `ACTIVE_STATES`/`SUBMITTED_STATES`/`AMBIGUOUS_STATES` 상수, `submitted_orders()`, 실행 잠금 `acquire_execution_lock`/`release_execution_lock`(`CONTROL#LIVE_EXECUTION_LOCK`, 120초 만료, 소유자만 해제), `apply_order_book()`(미체결 매수 금액·종목을 노출·보유 수에 더함, 같은 종목 당일 매수 수, 모호 주문 수).
- `live_cli.py`: `live-execute`가 잠금 획득 후 `_execute_locked` 실행. 증권사 계좌가 설정 계좌 하나와 같을 때만 지문 생성(`_verified_account_fingerprint`, baseline·supervise에도 적용, supervise는 확인 실패 시 빈 지문으로 kill switch). 계좌 전체 `holding_mismatches`가 비어야 `holdings_reconciled`. 시세 `date`/`tm` 없으면 거부. 환경변수 `LIVE_MAX_DAILY_BUY_ORDERS_PER_CODE`. README 실거래 절에 설명 추가.
- 테스트 추가 10개: `test_live_broker` 4(프로그램분만 한도, 연속 페이지, 페이지 무한 시 실패, 계좌번호 정규화), `test_order_safety` 1, `test_live_execution` 2(잠금 단일 소유·만료, order book), 새 `test_live_cli.py` 3(시세 시각 필수, 계좌 일치·불일치·복수·빈 값). 가짜 응답만 사용, 외부 통신 없음.
- 검증(PC-D): 실거래 4개 모듈 35개 OK. 전체 393개 실행, 실패 9건(`botocore` 미설치 로드 오류 5·`storage_contract_scope` 1, `truststore` 관련 `test_telegram_setup` 4 — 위 09:29 기록과 같은 9건), 새 실패 없음. `compileall -q src tests tools infra` 통과, `git diff --check` 통과.
- 남은 위험·미확인: `_execute_locked` 전체 흐름(잠금→계좌 대조→대사→승인→주문)을 묶은 통합 테스트는 없다(구성 함수별 테스트만). 실제 `ka00001` 응답이 계좌 여러 개일 때의 형식, `kt00018` 연속 조회 동작은 실계좌로 미확인. 실행 잠금은 `DeleteItem` 권한이 필요하므로 A3 실거래 템플릿 IAM에 포함해야 한다. 모의 경로 파일(`aws_runtime.py`·`engine.py`·`paper_*`·batch 템플릿)은 바꾸지 않아 11/02 배포 대상 불변.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 변경 없음, 실제 주문 없음. commit 없음, push 없음.

### 2026-10-28 PC-D / Claude → PC-C / 병행계획 A1: 실거래 안전 기능 점검(읽기만, 수정 없음)

- 범위: `order_safety.py`, `live_broker.py`, `live_execution.py`, `live_cli.py`와 `test_order_safety`·`test_live_broker`·`test_live_execution`을 읽었다. 코드·테스트 수정 없음, 테스트 미실행.
- 이미 있는 보호: 기본 `LIVE_ORDER_ENABLED` 꺼짐, kill switch 기록 없으면 ON, 승인 challenge가 주문 전체에 묶임(가격 바꾸면 무효), 승인·주문 TTL 300초, READY→SUBMITTING 조건부 claim으로 같은 주문 중복 차단, 주문 후 예외는 UNCERTAIN·자동 재주문 없음, 매도는 프로그램 수량·보호 기준선 초과분만, 기준선 write-once, supervisor가 불일치 시 kill switch ON.
- 발견(우선순위 순): ① 계좌 지문이 증권사 응답이 아니라 환경변수 `KIWOOM_ACCOUNT_NUMBER`로만 계산된다. 토큰의 실제 계좌와 달라도 통과한다(`ka00001`이 `acctNo`를 반환함, 명세 확인). ② 노출금액·보유종목 수 한도에 기존 사용자 보유분이 포함된다(`account_risk_state`의 `open_rows` 전체). 기존 보유가 60만 원 이상이거나 2종목 이상이면 매수가 항상 거부된다. ③ `kt00018` 보유 조회가 첫 페이지만 읽는다(명세에 `cont-yn` 있음). 보유 종목이 많으면 기준선이 불완전한 채 write-once로 잠긴다. ④ `live-execute`가 `holdings_reconciled=True`를 고정으로 넘겨, 해당 종목 수량 ≥ 기준선+프로그램만 확인하고 계좌 전체 정확 대사는 하지 않는다. ⑤ 다른 주문끼리는 동시 실행 잠금이 없어 현금·노출 한도 검사가 경합할 수 있고, `event_id`가 시각을 포함해 같은 종목 주문을 다시 준비할 수 있다(종목·일별 주문 수 제한 없음). ⑥ `ka10007`에 `date`/`tm`이 없으면 시세 시각을 현재 시각으로 간주해 오래된 시세 검사를 통과한다. ⑦ 일 손실한도는 계좌 전체 실현손익(`ka10074`)만 본다. 사용자 수동 매매가 섞이고 미실현 손실은 빠진다. ⑧ 미체결 취소는 `live-supervise`를 수동 실행할 때만 동작한다.
- 다음: 사용자 결정 후 ①~⑥ 수정과 회귀 테스트(실거래 경로만, 모의 경로·11/02 배포 대상 불변). ⑦⑧은 A5 실계좌 조건과 함께 결정.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 변경 없음, 실제 주문 없음. commit 없음, push 없음.

### 2026-10-28 PC-D / Claude → PC-C / 새 운용 5회로 변경·실거래까지 병행 작업 묶음(문서만)

- 사용자 결정: 아래 기록의 새 3회 운용을 **5회(11/03·11/04·11/05·11/06·11/09 진입, 마지막 보고 11/10 09:40)**로 바꾼다. 조건 확인과 실거래 준비 판단용 5회 완료를 한 운용으로 묶는다. 동시에 할 수 있는 작업은 묶어서 진행한다.
- 새 문서: `docs/운영 검증/2026-10-28_실거래까지_병행작업계획.md` — 권장안, 묶음 A(~11/02, AWS 불필요: 실거래 안전 기능 점검·가짜 응답 테스트·잠긴 실거래 템플릿 작성·검증 계획·실계좌 조건 결정), B(11/02 PC-C 순서 고정, 승인 목록 사전 일괄 승인), C(모의 5회 중 병행: 실계좌 읽기 검증·잠긴 템플릿 배포 검토, 각각 별도 승인), D(11/10 이후 순서대로: 5회 판정 → 소액 실주문 → 정기 실거래 재승인).
- 변경 문서: 작업지시서·일정 문서의 3회 → 5회(제목, 결론, 일정표, 2-6 `sessions` 5개·`PmStart`/`PmEnd`/`AmStart`/`AmEnd`=새 1~5회차 날짜). 코드·템플릿·테스트 변경 없음, 테스트 미실행(문서만). `ALLOWED_SESSION_COUNTS`에 5가 이미 있다.
- 남은 위험: 운용 중 판정 코드를 배포하면 5회 기록이 다시 시작된다. 5회 모두 `NO_TRADE`면 매수·청산 경로 미검증. 묶음 A에서 모의 경로 파일을 바꾸면 11/02 배포 대상이 바뀌므로 11/10 이후로 미룬다. 회차 날짜는 계산값이며 실제 계획 파일로 미확인.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 변경 없음, 실제 주문 없음. commit 없음, push 없음.

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
7. 10절이나 보관 파일에서 기록이 충돌하면 양쪽 기록을 모두 원문대로 보존해 합친다.
   충돌 표시를 제거한 뒤 `python stock-automation/tools/handoff_archive.py rotate`로
   6번째 이후 기록을 다시 보관 파일로 옮기고 `PASSED`를 확인한다. 이 도구는 충돌 표시가
   남아 있으면 이동하지 않고 실패한다.

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
