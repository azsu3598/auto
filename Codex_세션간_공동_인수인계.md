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

### 2026-10-29 15:26 KST — PC-D / Claude → PC-C / closing-v0.5 조건부 추천 등급 구현(브랜치 커밋 `c160fc6`)

- 작업 위치: worktree `D:/Test-logic-v04` / `feature/closing-v0.4`, `94b8a57` 위에 커밋 `c160fc6` 1개. 새 브랜치 없음, main 병합 안 함. 명세: `docs/프로그램 설계/2026-10-29_조건부추천등급_수정명세.md`(main 작업 트리에 미추적 상태로 있음. 브랜치에는 넣지 않음).
- 구현:
  - `config.py`: `rule_version="closing-v0.5"`, `conditional_score_margin=10.0`, `conditional_risk_fraction=0.5`. 두 값은 학습 대상 아님(`learning.py` 변경 없음).
  - `models.Candidate`: `tier`·`tier_reasons` 필드 추가(기본값 있음). `Decision.to_dict()` 후보에 두 값 포함.
  - `engine.py`: `_tier()` 추가. `FULL`은 점수 ≥ `minimum_score`, 검증 촉매, 해당 지수 > −1.0%를 모두 충족. `CONDITIONAL`은 그 외 점수 ≥ `minimum_score − 10`이며, 못 채운 조건(`CATALYST_UNKNOWN`/`MARKET_WEAKNESS`/`SCORE_BELOW_MINIMUM`)을 `tier_reasons`에 기록. 그 아래는 등급 없음.
  - 정렬은 FULL → CONDITIONAL → 등급 없음 순이고 같은 등급 안에서는 점수순. `_diversify`는 정렬 뒤에 그대로 적용.
  - NO_TRADE 조건을 "1위 후보에 등급 없음"으로 변경. 사유 코드는 기존과 같음.
  - CONDITIONAL은 `build_position_plan(max_loss=5,000, max_allocation_pct=0.20)`로 호출. `risk.py` 변경 없음.
  - BUY `reason_codes`는 `("TOP_SCORE_SELECTED", "TIER_FULL"|"TIER_CONDITIONAL", "PAPER_EXECUTION_ONLY")`. `notes`에 등급, 조건부 사유, 손실 한도, 배분을 기록.
- 표시 경로:
  - CSV 원장: `outcome_code`에 이미 포함.
  - `reporting.py`: 보고서 BUY 절에 "추천 등급"과 "판단 코드" 줄을 추가하고, 후보 표에 등급 열을 추가.
  - `dashboard.py`: 등급·조건부 사유의 한국어 라벨을 추가하고, 선택 후보의 `tier_reasons`를 사유 목록에 표시.
  - `aws_runtime.py`: 매수 알림 payload에 `reason_codes`(TIER와 조건부 사유)를 추가.
  - `tools/rejection_report.py`: 하드 필터를 통과한 종목의 FULL/CONDITIONAL/등급 없음 수를 집계.
  - `README.md`(브랜치): 등급 표를 넣고 규칙 버전을 `closing-v0.5`·`day-trade-v0.3`으로 바꿈. 촉매 설명을 코드에 맞게 바꿈(검증 촉매만 최대 10점, 미검증 테마 강도는 0점).
- 바꾸지 않은 것: 하드 필터, 점수식, `day_trade.py`, `medium_term.py`, 실주문 코드와 설정.
- 테스트:
  - 명세의 10개 테스트를 추가했다. `test_engine.ClosingV05TierTests` 9개, `test_champion_config.test_rejects_champion_tuned_on_closing_v04` 1개.
    - 점수 65·60·55 같은 값은 `minimum_score`를 옮겨 상대 점수로 맞췄다.
    - 6번 테스트는 실제 점수가 FULL 기준+1점, CONDITIONAL 기준+약 9.6점이다.
  - 명세 외로 2개를 추가했다. 표시 경로 테스트 `test_tier_is_visible_in_ledger_report_dashboard_and_alert`, 그리고 `test_rejection_report`의 등급 집계 단언이다.
  - 기대값 변경은 버전 문자열 4곳이다. `test_risk` 1곳, `test_learning` 1곳, `test_champion_config`의 fixture `base_rule_version` 2곳(v0.4 → v0.5)이다.
- 전체 테스트: PC-D에서 이번에 실행했다(`stock-automation/tests`, `PYTHONPATH=../src`, `unittest discover`). **453개 실행, 통과 442, 실패 2·오류 7, skip 2.**
  - 9건 모두 패키지 없음(`boto3`/`botocore`/`truststore`)이 원인이며, 새 실패는 0이다(직전 기록과 같은 9건이고, 테스트 수는 +11).
  - `git diff --check` 통과.
- 미실행: PC-C 전체 테스트(boto3 계열 4개 모듈 포함). v0.3·v0.4·v0.5 replay 비교는 S3 자료가 필요하고 AWS 조회가 금지라 하지 못했다.
- 남은 위험:
  - CONDITIONAL은 재료 미확인 종목도 매수하므로 모의 매수 빈도가 늘어난다.
  - 5,000원 손실 한도로 1주가 안 되는 고가주(약 12만 원 초과, 현금 60만 원 기준)는 `POSITION_SIZE_ZERO`다.
- 실거래 상태: 변경 없음. 실거래 설정·비상정지·실계좌 Secret·실제 주문·AWS 변경 없음. 이미지 빌드·배포 안 함. push 안 함(사용자가 직접).
- 다음:
  - 11/03~11/10 운용은 main(`closing-v0.3`)으로 진행한다.
  - 운용이 끝나면 PC-C에서 브랜치 전체 테스트를 돌리고, replay로 v0.3/v0.4/v0.5를 비교한다. 조건부 매수 손익·승률은 따로 본 뒤 병합 여부를 결정한다.

### 2026-10-29 PC-D / Claude → PC-C / closing-v0.5 작업 브랜치 정정(문서만, 미커밋)

- 사용자 승인으로 바로 아래 15:20 기록의 "`feature/closing-v0.5` 분기"를 정정: 새 브랜치 없이 `feature/closing-v0.4`(`94b8a57`) 위에 이어서 커밋한다. v0.4 비교는 커밋 `94b8a57`로 한다. main 병합 금지는 동일.
- 변경 파일: `docs/프로그램 설계/2026-10-29_조건부추천등급_수정명세.md`(적용 시점과 순서), 이 문서. 코드 변경·테스트 실행 없음. 실거래·AWS 변경 없음. commit/push 안 함.

### 2026-10-29 15:20 KST — PC-D / Claude → PC-C / 추천 2단 등급(FULL/CONDITIONAL) 규칙 추가와 closing-v0.5 명세(코드 변경 없음, 미커밋)

- 배경: 사용자가 대화 추천 기준이 지나치게 엄격하다고 판단(10/21 이후 대화 추천 전부 NO_TRADE). `docs/실시간 데이터 확인` 대조 결과 Codex 시절(8월~10/7) 추천은 거래대금 100~300억대 중형주의 조건부 1종목이었고, 이번 14:58 Claude 스캔은 상위 30개(하한 약 600억)만 봐서 대형주만 남았다(조회 범위 실수).
- 사용자 승인으로 `AGENTS.md` 11절에 "Recommendation Tiers" 추가, 14절에 한 문단 추가. `CONDITIONAL`은 재료 미확인·시장 약세(지수 −3% 미만 하락)·거래대금 100억 이상을 완화하고 비중 절반(손실 약 5,000원)·취소 조건 필수. 차트 조건(VWAP·5분20·고가 근접)과 과열 제외는 완화하지 않음. 스캔은 상위 100개 이상.
- 15:04 재스캔(네이버 공개 API, 상위 100): 코스피 −1.14%·코스닥 −2.51%. 대화 조건부 후보 메리츠금융지주(138040) 131,400원(+6.40%, 고가 대비 −0.30%, VWAP·5분20 위, 거래대금 252억). 당일 재료 미확인·ATR 미조회·NXT 표시 Y(프로그램 KRX_1520에서는 제외 대상). 보고서·원장 판단 문단·추천 이벤트 CSV 행은 아직 작성하지 않음(14:58·15:04 분석 모두).
- 신규: `docs/프로그램 설계/2026-10-29_조건부추천등급_수정명세.md`(closing-v0.5). 하드 필터·점수식 불변. `score ≥ minimum_score − 10`(10 = 확인 재료 최대 가점) 구간과 재료 미확인·지수 −1% 이하 후보를 `CONDITIONAL`로 절반 크기(손실 5,000원·배분 20%) 매수, `reason_codes`에 `TIER_*`. `feature/closing-v0.4`에서 `feature/closing-v0.5` 분기, main 병합 금지, 11/10 운용 뒤 v0.3·v0.4·v0.5 리플레이 비교.
- 변경 파일: `AGENTS.md`, 위 명세, 이 문서(rotate 보관 파일 포함). Claude 메모(저장소 밖) 갱신. 코드·테스트 변경 없음, 테스트 미실행.
- 실거래 상태: 변경 없음. 실제 주문·AWS 호출 없음. commit/push 안 함(사용자가 직접).
- 다음: 프로그래머가 명세 구현 → PC-C 전체 테스트. 기존 미커밋 파일(13:23 보고서·원장·CSV)은 그대로 둠.

### 2026-10-29 PC-D / Claude → PC-C / closing-v0.4 손절 폭 초과 후보를 순위 전에 제외(브랜치, 미커밋)

- 작업 위치: worktree `D:/Test-logic-v04` / `feature/closing-v0.4`, 기준 `977262b` + 11:10 명세 구현 기록의 미커밋 변경 위. 이 기록은 `main` 작업 트리 `D:/Test`에 적었다.
- 문제: `evaluate()`가 점수 1위에만 `atr_stop_rejection`을 적용해, 1위가 `STOP_TOO_WIDE`면 정상인 2위가 있어도 NO_TRADE였다.
- 수정: `src/stock_automation/engine.py` `rejection_reason()`에서 `ATR_UNAVAILABLE` 바로 다음에 `atr_stop_rejection(entry_price=q.best_ask or q.price, support_price=q.support_price, atr14=q.atr14, policy=cfg.atr_stop_policy)` 결과가 있으면 `STOP_TOO_WIDE` 반환. `evaluate()`의 기존 검사는 방어용으로 유지. ATR 수치(0.5/0.5/1.5%/5%/7%) 불변. 안전 필터 완화 없음(필터 추가만).
- 테스트: `test_engine.ClosingV04Tests.test_too_wide_top_scorer_is_skipped_for_the_next_candidate` 신규(필터 없이는 점수 1위인 손절 초과 종목이 `rejection_reasons()`에 `STOP_TOO_WIDE`, `rank_candidates()`에 없음, 2위 BUY·손실 ≤ 10,000원). **기대값 변경 1건**: `test_stop_wider_than_the_limit_is_recorded_as_stop_too_wide` — 유일 후보가 순위 전에 제외되므로 NO_TRADE 사유 `STOP_TOO_WIDE` → `NO_QUALIFYING_CANDIDATE`, `rejection_reasons()`가 `STOP_TOO_WIDE`를 표시하는 단언 추가(이 테스트는 11:10 명세 구현 기록에서 추가한 미커밋 테스트). `tests/test_day_trade.py`는 이번에 변경 없음(11:10 명세 구현 기록의 버전 문자열 1줄 외 기대값 불변).
- 전체 테스트(PC-D 이번 실행, `stock-automation`, `PYTHONPATH=src`, `unittest discover -s tests -v`): **442개 실행, 통과 431, 실패 2·오류 7, skip 2**. 9건 모두 패키지 없음(`boto3`/`botocore` 5, `truststore` 4)으로 새 실패 0. `compileall -q src tests tools infra` 통과, `git diff --check` 통과.
- 미실행: PC-C 전체 테스트, 백테스트 비교(replay 기록은 S3에만 있음, AWS 조회 금지).
- 남은 위험: 15:10 DART 조회는 하드 필터 통과 종목만 하므로, 15:10에 손절 폭 초과로 빠진 종목이 15:20 시세로 통과해도 `DART_NOT_CHECKED`로 차단된다(안전 쪽). `evaluate()`의 방어 검사는 정상 경로에서 도달하지 않는다.
- 실거래 상태: 변경 없음. 실거래 설정·비상정지·실계좌 Secret·실제 주문·AWS 변경 없음. main 병합·이미지 빌드·배포 안 함. commit/push 안 함(사용자가 직접).
- 다음: 사용자 커밋 후 PC-C에서 브랜치 전체 테스트. 11/10 5회 운용 종료 뒤 replay 백테스트 비교로 병합 여부 결정.

### 2026-10-29 PC-D / Claude → PC-C / 11:10 명세 구현(브랜치) 검토(읽기·테스트만, 코드 변경 없음)

- 대상: worktree `D:/Test-logic-v04` / `feature/closing-v0.4`(기준 `977262b`, 미커밋 12개)와 `main`의 `stock-automation/README.md` 수정. 아래 11:10 기록과 실제 diff 대조.
- 일치: 명세 1~5번이 기록대로 구현됨. `AtrStopPolicy`·`_tick_floor`·`ATR_UNAVAILABLE` 하드 필터·`STOP_TOO_WIDE`·검증 촉매만 가점·VWAP/5분 거래량 누락 처리·단타 VWAP 이격·챔피언 `base_rule_version`. 정책 없는 `build_position_plan`은 기존 식 그대로라 단타 손절 불변. 실거래·주문·AWS 템플릿 파일 변경 없음. README 정정 4곳은 코드와 일치.
- 재실행(PC-D, `PYTHONPATH=src`): 집중 5개 모듈 56개 OK, 전체 441개 실행·실패 2·오류 7·skip 2 — 9건 모두 `boto3`/`botocore`/`truststore` 없음, 기록과 같다. `test_runtime_safety`·`test_scheduled_execution`·`test_paper_control`·`test_worker_verifier`는 PC-D에서 로드되지 않아 PC-C 확인 필요.
- 동작 확인: 진입 10,000원 기준 ATR 7.0%까지 계획 생성, 7.2% 이상은 `STOP_TOO_WIDE`(비상손절 7% 상한이 먼저 걸림). 즉 일봉 ATR이 가격의 약 7%를 넘는 종목은 종가배팅에서 빠진다.
- 보완 권장(버그 아님, 명세가 모호했던 부분): ① `STOP_TOO_WIDE`를 1위 후보에만 적용해 2위가 조건을 만족해도 NO_TRADE가 된다. 변동성 큰 종목이 1위가 되기 쉬우므로, 손절 폭 검사를 `rejection_reason` 하드 필터로 옮겨 순위 전에 걸러내는 쪽을 권장. ② 기준 버전이 다른 챔피언을 조용히 무시하므로 실행 결과에 경고 표시를 남길 것(낮음). ③ 병합 전 브랜치 README의 규칙 버전·ATR 손절 설명 갱신(기록에 이미 있음).
- 변경 파일: 이 문서(기록 추가)와 rotate 보관 파일만. 코드 변경 없음.
- 실거래 상태: 변경 없음, AWS 호출 없음, 실제 주문 없음. commit/push 안 함.
- 다음: 사용자가 ① 권장안 반영 여부를 프로그래머에게 지시 → PC-C 브랜치 전체 테스트 → 5회 운용(11/10) 후 병합 판단.

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
