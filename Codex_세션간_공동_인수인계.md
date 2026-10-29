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

### 2026-10-29 11:10 KST — PC-D / Claude → PC-C / 매매 로직 수정 명세 1~5번 구현(브랜치, 미커밋)

- PC alias / 도구: `PC-D` / Claude. 작업지시: 사용자가 붙여 준 "매매 로직 수정 담당" 지시서. 명세: `docs/프로그램 설계/2026-10-29_매매로직_수정명세.md`.
- 브랜치·기준 commit: 시작 시 dirty 6개는 사용자 승인으로 `d043458`(단타 기록)·`977262b`(명세) 커밋. 5번(README)은 `main` 작업 트리 `D:/Test`, 1~4번은 git worktree `D:/Test-logic-v04` / 브랜치 `feature/closing-v0.4`(기준 `977262b`). 5회 모의운용(11/03~11/10) 전이므로 main 병합·이미지 빌드·ECR·AWS 배포 안 함. **11/02 배포는 `main`(현재 코드, `closing-v0.3`)으로 한다.**
- 변경 파일(`main`): `stock-automation/README.md`(명세 5절 4곳: 촉매 필수 문구 → 가점, `closing-v0.2` → `v0.3`, 테마 강도는 v0.3에서 미검증이어도 최대 6점 반영됨을 사실대로 기재), 이 문서·rotate 보관 파일.
- 변경 파일(브랜치): `src/stock_automation/risk.py`(`AtrStopPolicy`, `_tick_floor`, `atr_stop_rejection`, `build_position_plan(atr14=, atr_policy=)` — 정책 없으면 기존 고정 비율 그대로), `config.py`(`closing-v0.4`, `soft_atr_mult` 0.5·`hard_atr_mult` 0.5·`min_stop_pct` 1.5·`max_stop_pct` 5.0·`max_hard_stop_pct` 7.0, `atr_stop_policy`), `engine.py`(하드 필터 `ATR_UNAVAILABLE`(DART 검사 다음), 1위 후보 손절 초과 시 NO_TRADE `STOP_TOO_WIDE`, 검증 촉매일 때만 `catalyst_score` 가점, VWAP 없으면 5점·`ABOVE_VWAP` 제외+`VWAP_UNKNOWN`, 5분 거래량 배율 없으면 0점+`INTRADAY_VOLUME_UNKNOWN`), `day_trade.py`(`day-trade-v0.3`, `maximum_vwap_distance_pct` 3.0 초과 제외, 2.0% 초과 1%p당 3점 감점+`LATE_ENTRY_RISK`, `vwap <= 0` 제외), `learning.py`(챔피언에 `base_rule_version` 저장, 불일치·누락 챔피언 `config_from_champion` 거부), `aws_runtime.py`(15:20·주간 튜닝에서 기준 버전 불일치 챔피언은 무시하고 코드 기본값 사용), `tools/rejection_report.py`(`ATR_UNAVAILABLE`·`STOP_TOO_WIDE` 라벨). 새 상수는 learning 자동 조정 대상(5개)에 넣지 않았다.
- 추가 테스트: 새 `tests/test_risk.py` 9개(작은/큰 ATR, 손절 5%·비상 7% 초과, ATR 없음·0·음수·NaN, 호가 경계 2,010·5,020·20,100·50,200원 내림, 손실 ≤ 10,000원, 정책 없을 때 고정 비율 값이 `main` 결과와 동일), `test_engine.ClosingV04Tests` 7개, `test_day_trade.DayTradeVwapDistanceTests` 5개(+1.0%/+2.5%/+3.5%/VWAP 0, 기본 fixture 점수 90.8284 고정), `test_champion_config` 1개, `test_learning` 단언 추가.
- 기대값·fixture 변경(이유): ① `test_engine.quote()` fixture에 `atr14=600.0`(이 fixture에서 v0.4 손절이 기존 손절과 같아지는 값), `vwap=19_700`·`five_min_volume_ratio=1.8`(기존 대체값과 같은 값, 키움 경로는 항상 채움) 추가 — 이 fixture를 쓰는 엔진·aws_runtime·backtest·learning·reporting 테스트의 기대값은 그대로. ② `test_engine.test_catalyst_is_scored_not_required`: 검증−미검증 차이 4.0 → 8.8, 미검증−촉매 없음 4.8 → 0.0(명세 2번 의도된 변경). ③ `test_day_trade.test_creates_isolated_paper_position`: `"day-trade-v0.2"` → `"day-trade-v0.3"`(지시된 버전 상향으로 불가피. 지시서의 "test_day_trade 기존 기대값 불변"과 충돌하는 유일한 줄이며, 점수·손절·수량 기대값은 하나도 바뀌지 않음). ④ `test_champion_config` payload에 `base_rule_version: closing-v0.4` 추가(기대값 동일).
- 전체 테스트(PC-D 이번 실행, 시스템 Python 3.13, `PYTHONPATH=src`): 브랜치 **441개 실행, 통과 430, 실패 2·오류 7, skip 2**. 실패·오류 9건 모두 패키지 없음(`boto3`/`botocore` 5, `truststore` 4)으로 기존 PC-D 환경 실패와 같음. `main`(README만 변경) 419개 실행, 같은 9건. `compileall -q src tests tools infra` 양쪽 통과, `git diff --check` 양쪽 통과. worktree에는 Git 제외 서브모듈 `Kiwoom-REST-API`가 비어 있어 `D:/Test` 로컬 사본을 같은 commit `234560d`로 복제했다(네트워크 없음).
- 백테스트 비교: **비교 불가.** `replay-cases/`는 S3에만 있고 저장소에 기록이 없다. AWS 조회는 지시서상 금지.
- 미확인: PC-C 전체 테스트(완료 판정 기준) 미실행. S3 `config/rules/*.json` 챔피언 존재 여부 미확인 — 있으면 v0.4 배포 후 무시된다(의도). 브랜치 README의 규칙 버전 표·ATR 손절 설명은 `main` README 수정과 충돌하지 않도록 아직 v0.4로 바꾸지 않았다(병합 시 갱신 필요). 작업 중 Claude Code 프로세스가 한 번 비정상 종료(0xC0000409)됐으나 작업 트리 변경은 보존됨을 확인했다.
- 남은 위험: ATR 손절 초과·ATR 없음으로 `NO_TRADE`가 늘 수 있다(안전 쪽). 1위 후보가 `STOP_TOO_WIDE`면 2위로 넘어가지 않고 NO_TRADE다(명세대로). 단타는 VWAP가 없을 때(키움 어댑터가 0.0을 넣음) 이전에는 통과했으나 이제 제외된다. 제안값은 5회 기록·replay 백테스트 없이 채택한 초기값이다.
- 실거래 상태: 변경 없음. `LIVE_ORDER_ENABLED`·비상정지·실계좌 Secret·AWS·예약 변경 없음, 실제 주문 없음. commit/push 안 함(사용자가 직접).
- 다음: 사용자가 `main`(README·이 기록·보관 파일과 차트 수업 세션 변경)과 브랜치(`D:/Test-logic-v04`)를 각각 커밋. PC-C는 브랜치를 받아 전체 테스트를 실행하고, 5회 운용(11/10) 종료 뒤 S3 replay 백테스트 비교 → 병합 여부를 사용자에게 받는다.

### 2026-10-29 PC-D / Claude → 다음 세션 / 차트 기초 1강 학습 기록(문서만)

- 작업 경로: `D:/Test`, `main` / `42f44bb`(미커밋 상태 위에서 작업).
- 요청: 사용자 차트 기초 수업(캔들 네 가격·양봉/음봉과 등락률 기준 차이·종가 위치) 진행과 숙제 채점.
- 변경 파일: `Sabu/README.md` "현재 학습 기록"에 2026-10-29 한 줄 추가, 이 문서(기록 추가)와 rotate로 보관 파일.
- 테스트: 코드 변경 없음, 실행 안 함.
- 같은 날 앞선 기록(매매 로직 수정 명세)과 별개다. 명세·프로그래머 프롬프트는 변경 없음.
- 실거래 상태: 변경 없음, AWS 호출 없음, 실제 주문 없음. commit/push 하지 않음(사용자가 직접).
- 다음: 차트 수업 2강(음봉 꼬리 복습 → 교재 3장 추세·지지·저항).

### 2026-10-29 PC-D / Claude → 수정 담당 프로그래머 / 매매 로직 검토와 수정 명세(문서만, 코드 변경 없음)

- 작업 경로: `D:/Test`, `main` / `42f44bb`. 시작 시 사용자 미커밋 문서 3개(`docs/실시간 데이터 확인/` 2개, `docs/프로그램 설계/추천_이벤트_현재본.csv`)는 건드리지 않았다.
- 요청: 현재 자동매매 로직 검토 → 수정할 로직을 전문 프로그래머에게 전달할 설명으로 작성.
- 읽은 코드: `engine.py`·`config.py`·`risk.py`·`exit_engine.py`·`indicators.py`·`day_trade.py`·`learning.py` 일부·`providers/kiwoom.py` 시세 조립부.
- 발견(상세는 새 명세): ① 종가배팅 손절·목표가가 사실상 -2.5%/-4.5%/+3.8%/+6.2% 고정(지지선이 VWAP·5분 20이평 위 최댓값이라 `min(support, entry×0.975)`가 거의 항상 비율 쪽), ATR 미사용, 손절 폭 상한 없음. ② 미검증 키움 테마 강도가 `engine.py:254`에서 최대 6점. ③ 단타 VWAP 이격 상한 없음. ④ VWAP/5분 거래량 누락 시 대체값 가점·이중 계산(키움 경로 영향 없음). ⑤ README의 "검증 촉매 필수"·`closing-v0.2` 문구가 코드와 불일치.
- 변경 파일: `docs/프로그램 설계/2026-10-29_매매로직_수정명세.md`(신규), 이 문서(기록 추가), rotate로 보관 파일.
- 테스트: 코드 변경 없음, 단위 테스트 미실행. `risk.build_position_plan` 계산값만 PC-D Python으로 직접 확인.
- 남은 위험: 명세의 제안값(ATR 배수·손절 상한 등)은 사용자 미확정. 전략 변경(1~4번)은 11/03~11/10 5회 모의운용 종료 후 적용해야 5회 기록이 유지된다. S3 학습 챔피언 파일 존재 여부 미확인.
- 실거래 상태: 변경 없음, AWS 호출 없음, 실제 주문 없음. commit/push 하지 않음(사용자가 직접).
- 다음: 11/02 PC-C 작업은 기존 지시서대로. 명세 5번(README 정정)은 언제든 가능, 1~4번은 5회 운용 후 사용자 제안값 확정 뒤 착수.

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
