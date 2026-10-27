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

### 2026-10-27 15:30 KST — PC-D / Claude → PC-C / 탈락 사유 집계 도구 추가 (기존 스냅샷 읽기 전용 분석)

- 시각 정정: 바로 아래 기록 제목의 `15:50`은 작성 시 잘못 적은 시각이다. 실제 작성은 15:2x KST였다. 기록 원문은 규칙상 수정하지 않고 여기서 정정한다.
- 요청: 운용 중인 스택을 건드리지 않고 과거 NO_TRADE의 탈락 사유를 바로 집계. PC-D에서 도구와 테스트를 작성했고 **PC-C는 코드 수정 없이 실행만** 한다.
- 추가 `stock-automation/tools/rejection_report.py`: 이미 내려받은 `*-snapshot.json`을 읽어 `ClosingBetEngine.rejection_reasons`로 파일별·전체 탈락 사유를 표로 출력한다. 오프라인 전용이며 AWS 클라이언트·주문·파일 쓰기가 없다. `--snapshot <파일>`(반복 가능) 또는 `--dir <폴더>`(하위의 `*-snapshot.json` 재귀 검색), `--json` 지원. 읽지 못한 파일은 중단 없이 목록으로 보고하고, 처음 걸린 사유 하나만 센다. 기본 `StrategyConfig`를 쓰므로 챔피언 규칙 값은 반영되지 않는다.
- 추가 테스트 `stock-automation/tests/test_rejection_report.py` 3개(여러 파일 집계·비율, 깨진/없는 파일 보고, 입력 필수·읽기 전용). PC-D에서 통과.
- PC-D 전체 테스트: 358개 실행, 실패2·오류7~9(실행마다 달라짐)·skip2. 고정 실패 9건은 변경 전과 같은 환경 요인(`boto3` 미설치 7, 텔레그램 TLS 모킹 2)이고, 가끔 추가되는 1건은 `test_handoff_archive.HandoffTransactionTests.test_operating_system_releases_lock_after_process_exit`(프로세스 잠금, 변경과 무관해 보이나 원인 미조사)이다. 새 테스트는 모두 통과.
- **PC-C 실행 순서(코드 수정 없음, 읽기 전용)**: ① 테스트(위 15:50 기록 순서)를 먼저 끝낸다 ② 사용자 승인 하에 AWS CLI **읽기 명령**으로 과거 실행의 스냅샷만 내려받는다. 대상은 `runs/<YYYY>/<MM>/<DD>/KRX_1520/` 아래 `scan_1450-snapshot.json`·`shortlist_1510-snapshot.json`·`entry_1520-snapshot.json`이며 버킷 이름은 PC-C 인수인계의 값을 쓴다. 쓰기·삭제·`--delete`를 쓰지 않고, 내려받은 폴더는 Git에 올리지 않는다(스냅샷은 시세 원본이므로 저장소 밖 임시 폴더 사용). ③ `"C:\Test\.venv\Scripts\python.exe" stock-automation\tools\rejection_report.py --dir <내려받은 폴더>`를 실행해 출력 표를 이 문서나 사용자 대화에 그대로 옮긴다. ④ 스냅샷에 계좌·키 정보는 없어야 하며, 의심되면 출력하지 말고 중단한다.
- 한계: 1~5회 운용의 15:10/15:20 스냅샷이 모두 S3에 남아 있는지는 확인하지 못했다. 없거나 `delayed`인 파일은 도구가 "읽지 못한 파일"로 보고한다. 이 집계는 AWS 반영 전에도 가능하며 앱 이미지 변경이 필요 없다.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 예약 변경 없음, 실제 주문 없음.

### 2026-10-27 15:50 KST — PC-D / Claude → PC-C / PC-C는 코드 수정 없이 테스트 실행·기록만 (템플릿 재생성 완료)

- 사용자 지시: 코드 수정은 PC-D가 최대한 끝내고 **PC-C는 테스트 실행과 기록만** 한다. 아래 15:14 기록의 PC-C 순서 중 코드·산출물 수정이 필요한 부분을 PC-D에서 미리 처리했다.
- PC-D가 처리: 11:16 기록이 PC-C 몫으로 남긴 `stock-automation/infra/paper-five-session-batch.yaml` 재생성을 완료했다. 빌더는 기존 출력 파일을 덮어쓰지 않으므로(`Preserve existing output`) 임시 경로에 생성해 저장본과 비교한 뒤 교체했다(차이는 `Resources`뿐이며 11:16 paper_batch.py 텔레그램 문구 반영분). 따라서 PC-C는 **템플릿 재생성을 하지 않는다.** 재생성 후 `test_saved_template_matches_builder_exactly`는 통과한다.
- PC-D 전체 테스트(시스템 Python 3.13, `unittest discover`): 355개 실행, 실패2·오류7·skip2. 변경 전 커밋 `49aec1c`를 같은 방법으로 돌린 결과와 비교해 **새로 생긴 실패 없음**(템플릿 실패1건은 재생성으로 해소). 남은 9건은 이 PC 환경 요인으로 변경 전에도 동일하다: `boto3`/`botocore` 미설치로 `test_paper_control`·`test_runtime_safety`·`test_scheduled_execution`·`test_worker_verifier`·`test_storage_contract_scope` 오류, 텔레그램 TLS 모킹 `test_telegram_setup` 3건. 이 PC에는 저장소 `.venv`가 없어 AWS 의존 테스트는 PC-D에서 검증하지 못했다.
- **PC-C 할 일(코드 수정 없음)**: ① pull 후 세 문서 재확인 ② `C:\Test\.venv\Scripts\python.exe`로 전체 테스트와 compileall 실행(AWS 의존 테스트 포함) ③ 결과를 있는 그대로 기록하고 rotate ④ 이미지·Lambda 반영은 사용자 승인 후 11/03 이후. **테스트가 실패하면 코드를 고치지 말고 실패 테스트명과 오류 원문만 기록해 PC-D에 넘긴다.** 실패 테스트를 수정·삭제하거나 안전 검사를 완화하지 않는다.
- 기대 결과: PC-D에서 `boto3` 때문에 못 돌린 테스트가 PC-C에서는 통과해야 한다. 만약 PC-C에서 위 9건 외의 실패가 나오면 PC-D 변경이 원인일 수 있으므로 원문을 기록한다.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 예약 변경 없음, 실제 주문 없음.

### 2026-10-27 15:14 KST — PC-D / Claude → PC-C / 15:10 후보 선별 탈락 사유 기록 추가 (코드만, 전체 테스트 미실행)

- 요청: 종가배팅이 계속 `NO_TRADE`인 이유를 필터 완화 전에 숫자로 확인하기 위해, 후보 선별에서 종목별 탈락 사유를 남긴다. 기존에는 통과 종목 코드·점수만 저장돼 36건이 왜 전부 탈락했는지 알 수 없었다. 사용자 지시로 PC-D에서는 코드만 작성했고 커밋·push·AWS 반영은 하지 않았다. 적용은 PC-C가 진행한다.
- 변경 `stock-automation/src/stock_automation/engine.py`: `ClosingBetEngine.rejection_reason(snapshot, quote)`를 추가해 기존 하드 필터를 **같은 순서**로 검사하고 처음 걸린 사유 코드를 반환한다(`STALE_QUOTE`, `NXT_ELIGIBLE_EXCLUDED`, `PRICE_OUT_OF_RANGE`, `LOW_TRADING_VALUE`, `LOW_VOLUME_RATIO`, `WEAK_CLOSE_STRENGTH`, `DAY_CHANGE_OUT_OF_RANGE`, `BELOW_5M_MA20_OR_FALLING`, `INVALID_SUPPORT`, `EXTENDED_FROM_MA5`, `BELOW_VWAP`, `RSI_OUT_OF_RANGE`, `CATALYST_NOT_VERIFIED`, `MARKET_DECLINE_GATE`). `rejection_reasons(snapshot)`는 탈락 종목코드→사유 딕셔너리를 반환하며 지연 스냅샷은 기존처럼 `ValueError`로 거부한다. `_score_quote`는 이 함수를 호출하도록 바꿨고 필터 조건·순서·점수 계산은 바꾸지 않았다.
- 변경 `stock-automation/src/stock_automation/aws_runtime.py`: `SHORTLIST_1510`의 `shortlist.json`에 `rejection_reasons`(종목별)와 `rejection_counts`(사유별 건수)를 추가한다(`collections.Counter` import 추가). 기존 키 `codes`·`quotes`·`scores`는 그대로이며 15:20 단계는 `codes`·`quotes`만 읽는다. 필터·진입·손절·안전 기준 변경 없음.
- 추가 테스트 `stock-automation/tests/test_engine.py` 3개: 첫 실패 필터가 사유로 기록됨(여러 조건 동시 실패 시 앞선 것), 탈락 목록과 `rank_candidates` 결과가 서로 겹치지 않고 일치, 지연 스냅샷 거부.
- 검증(PC-D): `python -m unittest tests.test_engine` 19개 OK(기존16+신규3), `py_compile aws_runtime.py` 통과. **전체 테스트·compileall은 실행하지 않았다.** `shortlist.json` 저장 부분은 큰 함수 안에 있어 단위 테스트가 없다.
- 한계: ① 한 종목이 여러 조건에 걸려도 **처음 걸린 사유 하나만** 기록한다. ② 테마 중복 제외와 점수 60점 미만 탈락은 집계하지 않는다(하드 필터 탈락만). ③ 새 앱 이미지를 빌드·게시하고 ECS 템플릿 `ImageUri` digest를 갱신하기 전에는 AWS에 반영되지 않는다.
- **PC-C 순서**: pull 후 세 문서 재확인 → 집중 테스트(`tests/test_engine.py`, `tests/test_aws_runtime.py`) → 전체 테스트·compileall → 결과 그대로 기록. 앱 이미지 반영은 위 11:16 기록의 위험(운용 중 이미지 변경 시 `PRODUCTION_TASK_CHANGED` 등)과 같으므로 5회 운용 종료(11/03) 후 또는 새 승인 계획에서 11:16·11:24 수정과 함께 한 번에 반영하는 것을 권장한다. 반영 후 첫 15:10 실행의 `shortlist.json` `rejection_counts`를 보고 탈락 상위 사유를 확인한다.
- 참고(대화 기록 아님): 같은 날 14:21·15:01 대화형 점검에서 거래대금 상위가 반도체·AI 부품에 쏠리고 나머지는 급등 추격 또는 촉매 미확인이어서 확정 추천 0건이었다. 필터 완화 여부는 위 집계를 모은 뒤 사용자와 결정하며, 이번 작업은 필터를 바꾸지 않았다.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 예약 변경 없음, 실제 주문 없음. commit/push 없음.

### 2026-10-27 11:24 KST — PC-D / Claude → PC-C / 상세 알림 확인용 2회 모의운용 허용 (코드만, 테스트 미실행)

- **PC-C 필독:** 이번 작업은 `docs/운영 검증/2026-10-27_PC-C_작업지시_알림개선_2회운용.md`의 순서만 따른다(pull → 템플릿 재생성 → 집중 테스트 → 전체 테스트 → 기록·rotate). AWS 변경, `stop`, 안전 검사 완화, 실패 테스트 수정·삭제는 금지이며, 실패하면 고치지 말고 오류 원문을 기록한다.
- 정정: 아래 11:16 기록의 템플릿 재생성 명령은 `stock-automation` 안의 `.venv`를 가리켜 잘못됐다. 가상환경은 저장소 루트 `C:\Test\.venv`이므로 작업지시서의 절대경로 명령(`"C:\Test\.venv\Scripts\python.exe" ...`)을 사용한다.

- 사용자 결정: 11:16 기록의 수정(15:10 시세0건 오분류 보완·텔레그램 한국어 설명)은 진행 중인 5회 운용에 반영하지 않고, 5회 운용 종료(11/03) 뒤 **별도 2회 모의운용**으로 확인한다. 목적은 더 상세한 알림을 실제로 받아 보는 것이다. PC-D에서는 코드만 작성했고 테스트·실행·AWS 변경은 없다.
- 변경: `stock-automation/infra/paper_batch.py`에 `ALLOWED_SESSION_COUNTS = (2, 5)`를 두고 회차 수 검사·이벤트 매칭·안내 문구(`Bounded N-session`, `회차: n/N`)를 계획의 회차 수 기준으로 바꿨다. 2·5 외 회차 수는 계속 거부한다. 오류 코드 이름 변경: `EXACT_FIVE_PAPER_SESSIONS_REQUIRED`→`APPROVED_PAPER_SESSION_COUNT_REQUIRED`, `OUTSIDE_APPROVED_FIVE_SESSIONS`→`OUTSIDE_APPROVED_SESSIONS`. `stock-automation/tools/paper_batch_checks.py`(회차 수 2·5 허용, 일정 시작·종료일은 기존처럼 계획 날짜로 정확히 검사), `stock-automation/tools/paper_operations.py`(2·5 허용, `bounded_sessions`를 실제 회차 수로 표시, 코드 `APPROVED_SESSION_BATCH_REQUIRED`). 15개 예약과 템플릿 구조는 회차 수와 무관해 바꾸지 않았다.
- 추가 테스트(미실행): `stock-automation/tests/test_paper_batch.py`, `test_paper_batch_checks.py`, `test_paper_operations.py`.
- 현재 5회 운용 영향: 이미 배포된 Lambda와 승인 계획은 그대로이며 이 커밋만으로 바뀌지 않는다. 현재 5회 계획은 새 코드에서도 유효하다.
- PC-C 할 일: 11:16 기록의 템플릿 재생성→테스트 순서에 이번 3개 테스트 파일을 포함한다. 2회 운용은 11/03 이후 새 계획으로 준비하며, 새 앱 이미지(11:16 수정 포함)·batch Lambda를 반영한 별도 승인 절차를 거친다.
- 직전 회차(parent) 보완(같은 세션 후속, 사용자 요청): 기존 parent는 단회 pilot 계획만 허용했다. `paper_batch.parent_reference()`를 추가해 `parent.kind`가 없거나 `pilot`이면 기존과 동일하게 처리하고, `kind: "batch_session"`이면 이전 batch의 **마지막 회차**를 parent로 쓴다. 이 형식의 parent는 `prefix`(이전 batch 루트, 예 `validation/batch/<이전 batch_id>`), `plan_key`, `plan_sha256`, `batch_plan`(이전 batch 불변 계획 전체)을 가진다. 이전 계획 전체를 `validate_batch`로 다시 검증하고, 새 첫 회차 진입일=이전 마지막 청산일, 이전 batch·pilot ID 재사용 금지, 마지막 회차 모든 단계 완료·실제 lease·판단/장부 일치·REPORT_AM 깨끗함·**ledger digest 일치**(pilot과 달리 필수)·서버 정지를 기존 `completed()`로 확인한다. 이전 batch 루트 STOP·HALT와 마지막 회차 STOP이 있으면 GATE와 DEPLOYMENT_CHECK 모두 거부(`PREDECESSOR_MANUALLY_STOPPED`/`PREDECESSOR_BATCH_HALTED`). 템플릿의 S3 읽기 권한은 이미 `${ParentPrefix}/*`·`${ParentPlanKey}` 기준이라 구조 변경이 없다. 테스트 `BatchSessionParentTests`(미실행).
- 남은 확인: 새 2회 계획에서 `ParentPrefix`를 이전 batch 루트로, `ParentPlanKey`를 이전 batch 불변 계획 키로 지정해야 한다. 이전 마지막 회차의 decision.json(`runs/2026/10/30/KRX_1520/decision.json` 등)이 새 스택의 `DecisionKey` 읽기 권한 범위에 드는지, 사전 검증(morning proof) 값을 무엇으로 둘지는 PC-C 계획 수립 때 확인한다. 회차 날짜·달력 승인과 AWS 반영은 사용자 승인 대상이다.
- 실거래 상태: 변경 없음, 실제 주문 없음. commit/push 없음.

### 2026-10-27 11:16 KST — PC-D / Claude → PC-C / 15:10 시세 0건 오분류 보완·텔레그램 한국어 설명 (코드만, 테스트 미실행)

- 요청: pull 확인 중 발견한 오분류 가능성 보완과, 모의운용 텔레그램 알림의 의미를 알 수 있게 수정. 사용자 지시로 PC-D에서는 **코드만 작성**했고 테스트·템플릿 재생성·실행·커밋·AWS 반영은 하지 않았다. 테스트와 적용은 PC-C가 진행한다.
- pull 확인 결과(수정 전): 작업 트리 clean, `origin/main`=`9d08d91`. `handoff_archive.py check` PASSED, `fd5e829→c12ab43→9d08d91` 기록 누락·변경0·순서 유지. PC-D 임시 venv에서 전체402개 OK(skipped2)·compileall·recommendation-lab37개·Node 4+8+15개 통과(수정 전 코드 기준이며 이번 수정 결과가 아니다).
- 수정1 `stock-automation/src/stock_automation/aws_runtime.py`: 9d08d91은 15:10 shortlist가 빈 목록이면 `NO_QUALIFYING_CANDIDATE`로 분류해 15:10 시세 0건(데이터 장애)도 "기준 충족 종목 없음"으로 기록될 수 있었다. shortlist.json에 `quotes`(15:10 수신 시세 수)를 추가하고, `_shortlist_screened_empty()`가 빈 목록이면서 `quotes`>0인 경우만 선별 완료로 본다. `quotes` 없는 기존 파일·0건은 `MARKET_DATA_UNAVAILABLE` 유지. 필터·진입·안전 기준 변경 없음.
- 수정2 텔레그램(판단 로직 변경 없음, 문구만):
  - `stock-automation/infra/paper_batch.py`: 기존 코드 줄은 그대로 두고 아래에 한국어 설명(회차 n/5·진입일, 단계, 판단 BUY/NO_TRADE/NO_RECORD 의미, decision.json의 reason_codes·한국어 notes, 15:20/09:10 작업 상태, 열린 가상 포지션, RECONCILIATION_REQUIRED/BLOCKED_OR_FAILED와 HALT 안내, 실패 원인 코드 약40종)을 붙인다. 설명 생성이나 decision.json 읽기 실패 시 원래 메시지만 보내 보고가 실패/HALT로 바뀌지 않게 했다. `paper_pilot.py`(완료된 단회 pilot, 평문 인라인 템플릿)는 변경하지 않았다.
  - `stock-automation/src/stock_automation/notifications.py`: 청산 등 동작 코드(`SCHEDULED_EXIT` 등)를 한국어로 바꾸고 `사유:` 줄(대시보드 `_REASON_LABELS` 재사용)과 "실제 계좌 주문이 아닙니다" 안내를 추가.
  - `stock-automation/infra/paper_control.py`: 제어 오류 코드3종(`NETWORK_CONTROL_FAILED`, `TASK_CLEANUP_RECONCILE_REQUIRED`, `ECS_TASK_FAILED_RECONCILE_REQUIRED`) 의미 한 줄과 미분류 안내 추가.
- 추가 테스트(미실행): `stock-automation/tests/test_aws_runtime.py`, `test_notifications.py`, `test_paper_batch.py`, `test_paper_control.py`.
- **PC-C 순서**: ① `cd /d C:\Test\stock-automation` 후 `".venv\Scripts\python.exe" tools\build_paper_batch_template.py --output infra\paper-five-session-batch.yaml`로 템플릿 재생성(안 하면 `test_saved_template_matches_builder_exactly` 실패) ② 집중 테스트와 전체 테스트·compileall 실행, 실패 시 결과 그대로 기록 ③ 앱 이미지(aws_runtime·notifications, 9d08d91 수정 포함), batch Lambda(paper_batch), control Lambda 패키지(paper_control)는 각각 별도 반영 대상.
- 위험: 진행 중 5회 운용은 준비 검사에서 승인 당시 작업 정의·컨테이너 설정·plan hash를 대조한다. 운용 도중 이미지·Lambda를 바꾸면 `PRODUCTION_TASK_CHANGED`/`PAPER_CONTAINER_CHANGED`로 GATE가 막혀 HALT되거나, 반대로 batch가 승인된 이전 이미지를 계속 써서 수정이 적용되지 않을 수 있다(실제 대조 대상은 PC-C에서 확인 필요). 현재 5회 운용 종료(11/03) 후 또는 새로 승인된 계획으로 적용을 권장한다. 적용 전 알림은 기존 영문 형식 그대로다.
- 한글 깨짐 복원: 아래 `2026-10-26 PC-C / Korean explanations required in final five-session report` 기록의 `??` 두 곳을 사용자 요청으로 복원했다. 근거는 같은 커밋 `9d08d91`의 작업계획 문서이며, 경로 `docs/운영 검증/2026-10-23_5거래일_완료후_실거래준비_작업계획.md`와 문구 `근거 기록 없음`(문서 34행)이 깨진 글자 수와 정확히 일치한다. 그 외 기록 내용은 바꾸지 않았다. 깨지기 전 원문 바이트는 Git 이력에 없으므로 이 복원은 원본 문서 대조 결과다.
- 사용자 확인 사항: 10/27 09:40 REPORT_AM(`NO_TRADE`, 두 작업 COMPLETED, 열린 포지션0)과 09:45 `2026-10-27 GATE: READY`는 정상 결과로 설명했다. 10/26 NO_TRADE는 오류가 아니라 기준 통과 종목0(PC-C 10/26 기록 기준)이다.
- 실거래 상태: LIVE_ORDER_ENABLED·kill switch·실계좌 Secret·AWS 예약 변경 없음, 실제 주문 없음. commit/push 없음.
- 다음: PC-C는 pull 후 세 문서를 다시 읽고 위 순서대로 템플릿 재생성→테스트를 실행해 실제 결과를 기록한다. 적용 시점은 사용자와 별도 확인한다.

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
