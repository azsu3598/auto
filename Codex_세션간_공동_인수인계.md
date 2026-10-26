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

### 2026-10-26 20:52 KST — PC-C → PC-C / NO_TRADE 사유 오분류 수정

- 사용자 요청: `MARKET_DATA_UNAVAILABLE`와 필터 통과 후보 없음의 구분을 수정하고 커밋. 다른 PC에서는 실행하지 않고 수정만 하며 테스트·적용은 현 PC에서 진행한다고 확인했다.
- 10/26 저장 결과 확인: 14:50·15:10 KRX 조회 각 36건, 15:10 shortlist 0건, 15:20 entry 입력 quotes 0건. 따라서 실제 결과는 데이터 수신 실패가 아니라 후보 필터 통과 종목 없음이다. 기존 엔진은 빈 entry quotes만 보고 `MARKET_DATA_UNAVAILABLE`를 기록했다.
- 수정: `ClosingBetEngine.evaluate`에 선행 후보선별이 완료된 빈 shortlist 문맥을 전달하고, 해당 경우 `NO_QUALIFYING_CANDIDATE` 및 한국어 설명을 남긴다. 일반적인 시세 미수신은 계속 `MARKET_DATA_UNAVAILABLE`이며 기존 필터·모의 진입 및 안전 기준은 그대로다.
- 변경 파일: `stock-automation/src/stock_automation/engine.py`, `stock-automation/src/stock_automation/aws_runtime.py`, `stock-automation/src/stock_automation/dashboard.py`, `stock-automation/tests/test_engine.py`, `stock-automation/tests/test_dashboard.py`, `docs/운영 검증/2026-10-23_5거래일_완료후_실거래준비_작업계획.md`, 본 인수인계, 보관 인수인계.
- 검증: 집중 엔진 테스트 16개와 대시보드 테스트 12개 통과. 저장소 `.venv` Python 3.13.16에서 전체 테스트 402개 통과, 2개 skip. 기본 Python 3.14는 AWS SDK/의존성이 없어 사용하지 않았다. 템플릿의 이미지 참조와 연동 상태는 아직 적용 전이며 AWS에서 새 이미지를 사용한 검증은 미실행.
- 실패·미확인: 현재 ECS 템플릿은 기존 ECR 이미지 digest를 고정 참조한다. 이 소스 수정은 아직 해당 이미지에 포함되지 않았으므로 새 이미지 빌드·게시 후 해당 digest를 템플릿 `ImageUri`에 넣는 적용이 남았다.
- 안전: 이 작업에서는 AWS 배포, 스케줄 변경, 실계좌 연결, 실주문 없음. 기존 모의·실거래 분리와 모든 주문 안전장치는 유지.
- 다음: PC-C에서 새 앱 이미지를 별도 검토·빌드·게시하고, 정확한 digest를 사용하는 템플릿을 검증한 다음 기존 스택의 이미지 갱신만 진행한다. 테스트/적용은 PC-C에서 하고 PC-D에서는 실행하지 않는다.
- 실거래 상태: 비활성; 실제 주문 없음. 커밋은 본 기록·보관 회전 및 diff 점검 뒤 수행.

### 2026-10-26 PC-C / Korean explanations required in final five-session report

- User requested that, after current run completes normally, next report explain in Korean why each action/outcome occurred.
- Updated `docs/?? ??/2026-10-23_5???_???_?????_????.md`: report each BUY/SELL/NO_TRADE/HALT and other relevant action with Korean reason grounded in logs, decision inputs, quotes and ledger evidence; mark missing reason as `?? ?? ??`, never infer.
- No AWS or schedule changes and no source change. Report is due only after actual five-session completion. No test run required for this documentation clarification.
- Live order state unchanged; no commit/push.

### 2026-10-23 PC-C / Five-session completion and live preparation work plan

- User supplied admin CloudShell output DEPLOYMENT_VERIFIED and FIVE_SESSION_BATCH_ARMED;15/15 verified. This is user-run administrator evidence, not operator-side requery. Parent one-time validation remains required; no claim of actual completed trades.
- User requested next-work checklist based on five-session completion. Added dated2026-10-23 work plan under docs operations validation, covering evidence-based completion, NO_TRADE handling, final wallet/position/server reconciliation, failure branches, current live code review and separately approved live integration/order stages.
- Plan clarifies: one10/26 validation plus five follow-on entries10/27 through11/02, final exit/report11/03; all-NO_TRADE does not prove operational fill paths; internal ledger simulation is not broker order verification. Batch-aware status/review access remains a handoff concern.
- Inspected live_cli/live_execution/live_broker entry points; existing implementations must be audited instead of assumed absent. No new source-code tests run for this documentation-only task; previous399 test result is historical. No AWS calls, schedule changes, real orders, credentials, commit or push in this task.
- Next: follow the new work plan to collect five-session results; prepare live code/tests/templates while leaving live enablement and real-account secrets subject to separate explicit approval. No guaranteed live start date.

### 2026-10-23 PC-C / User reports batch-v3 CREATE_COMPLETE; operator review denied

- User reports CREATE_COMPLETE for batch-v3. Operator DescribeStacks attempt returned AccessDenied; remote creation result is not independently verified, and batch remains NOT confirmed armed.
- Prepared ignored runtime/paper_batch_v3_admin.py, a self-contained administrator CloudShell script embedding the exact follow-on template/plan. Helper files runtime/batch_admin_core.py and batch-admin-payload.json are also ignored. No credentials or secret values embedded; infrastructure references remain local runtime only.
- Script validates account/stack/template/parameters, deployed Lambda package/config/environment, all15 disabled schedule targets/retries/bounds; conditionally publishes the immutable plan and invokes DEPLOYMENT_CHECK. --arm explicitly enables stops first, entries last; reads back every update and rolls schedules back to DISABLED on failure. Parent completion/HALT checks remain in deployed code. Default invocation performs review and plan registration only.
- Validation: script py_compile and embedded payload/default check PASS. Actual administrator execution and rollback integration are untested. Existing full399 regression result predates this new operational script; no new full suite run claimed. No remote changes made in this turn. Await admin CloudShell upload/run; do not claim batch activated.
- One-time pilot remains previously ARMED_IN_AWS. No live orders/activation or commit/push. Existing handoff modifications preserved.

### 2026-10-23 PC-C / Authorized one-time activation and five-session preparation

- User authorized activation and requested five days. arm_paper_pilot_20261026_update.py succeeded: READINESS_VERIFIED and ARMED_IN_AWS; all15 events enabled/readback verified, independent stops first. Entry10/26 15:20 KST, exit10/27 09:10. No manual task/server start or real orders. Evidence runtime/paper-pilot-armed-20261026.json.
- Prepared five follow-on sessions, conditional on completed parent: entries10/27,10/28,10/29,10/30,11/02; final exit11/03. This interpretation means validation plus five additional sessions. Counting not explicitly confirmed by user.
- Ignored runtime outputs: prepare_paper_batch_20261026.py, paper-batch-console-20261026-followon.yaml, paper-batch-plan-20261026-followon.json, paper-batch-immutable-plan-20261026-followon.json. Candidate NEW stack stock-automation-paper-batch-v3. NEVER apply batch template to pilot. Fixed batch names retained; latest remote name conflicts unverified. No user-attached managed policy added.
- Local batch safety/calendar/date bounds/hash/default checks PASS. Template hash compares normalized UTF8 text, consistent with preparation tool; first byte-hash assertion failed due to Windows CRLF, corrected verification only. Immutable plan byte hash passes. No source or safeguards changed. Prior regression399 OK(skipped=2).
- Batch NOT deployed or activated. Remaining: admin creates separate batch-v3 with PilotState DISABLED; verify remote resources and DEPLOYMENT_CHECK; register immutable plan and bounded schedules only after review. Operator lacks batch access and may need administrator help; do not repeat oversized review policy update or bypass predecessor/HALT. Existing pilot one-time activation is complete; five-day operation is not yet complete.
- No live enablement, real orders, tracked source changes, commit or push. Remote kill switch not independently reverified.

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
