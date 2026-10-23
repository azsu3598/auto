# 버튼형 종목 추천 배포 전 개발분과 PC-C 검증 체크리스트

## 상태와 권한

2026년 10월 23일 PC-D 작업이다. 사용자가 버튼형 추천 기능의 **배포 전 가능한 개발을 승인**했고, **테스트 실행은 PC-C에서 직접 진행**하겠다고 지정했다. 이 문서가 초기 설계의 샘플까지만 승인되었다는 문구보다 우선한다.

**코드 작성 상태이며 테스트·실행·배포 성공 상태가 아니다.** PC-D에서는 Python·JavaScript 코드, 테스트 파일, 오프라인 샘플과 본 지침을 작성했을 뿐 새 서버를 시작하거나 테스트 명령을 실행하지 않았다. 실시간 추천 수집기·뉴스 자동 검증·AI·Cognito 연동은 미구현이다. 현재 모의운용을 중지하거나 바꿀 이유가 없다.

## 파일과 분리 구조

| 위치 | 용도 |
|---|---|
| `stock-automation/recommendation-lab/core.py` | 부작용 없는 연구 입력 검증·후보 선별·비중/위험 제안 |
| 같은 폴더 `service.py` | 1개 프로세스 내 중복 요청·동시 실행·쿨다운·유효기한 제한 |
| 같은 폴더 `server.py` | 수동 시작하는 localhost 전용 개발 API와 화면. 기존 앱의 서버가 아님 |
| 같은 폴더 `web/` | 버튼 요청·결과·실패·자료 만료·화면 대기 취소 UI |
| 같은 폴더 `package_lab.py` | 검토용 ZIP 생성기. 업로드·배포·기존 파일 덮어쓰기 없음 |
| 같은 폴더 `sample_input.py`, `tests/` | 가상 입력 생성·PC-C 실행용 테스트. 배포 검토 ZIP에서 제외 |
| `docs/prototypes/recommendation-preview/dist/index.html` | 별도로 더블 클릭할 수 있는 오프라인 화면 샘플 |
| `docs/prototypes/recommendation-preview/test-preview.cjs` | 오프라인 샘플의 가상 DOM 테스트 |

기존 `stock-automation/src/`, `infra/`, `tools/`, `web/`, Dockerfile, IAM, 배포 템플릿, 운영 대시보드는 이번 작업으로 변경하지 않는다. 새 폴더는 기존 Docker COPY와 웹 패키저 대상 밖이다. 기존 앱은 새 폴더를 import하거나 링크하지 않는다. 추천·매매 CSV/XLSX나 운영 원장을 쓰지 않는다.

사용자가 이미 갖고 있던 미커밋 변경은 별도다. Git diff가 많다고 전부 이번 추천 작업으로 간주하거나 이전 PC 작업을 되돌리지 않는다. 특히 CRLF/LF 차이를 임의 일괄 포맷으로 해결하지 않는다.

## 작성된 기능과 제한

- 버튼을 눌렀을 때만 POST 1회. 자동 시작·반복 감시·자동 재시도 없음. 기본 시작은 데이터 수집기가 없어 `DATA_SOURCE_NOT_CONNECTED`로 차단된다.
- 브라우저는 요청 ID만 전달한다. 계좌·실거래 모드·파일 경로·임의 URL·주문 입력은 거부한다. localhost Host/Origin/CSRF 검사와 정적 파일 allowlist를 둔다. 이 보호는 개발용이며 Cognito 인증·TLS·운영 보안을 대체하지 않는다.
- 서버가 지정한 연구 JSON만 읽는다. JSON 파일을 읽는 것은 시장 사실을 독립적으로 검증하는 기능이 아니다. 입력의 `verified` 표시는 추후 수집기의 책임과 증거 대조가 필요하다.
- 시각·지연·세션·거래소·NXT 자격·출처·일봉/분봉 지표·당일 기관/프로그램 수급·촉매·가격 구간·호가단위 검증 여부를 요구한다. 잘못된 필수 입력은 일부 성공이나 NO_TRADE로 숨기지 않고 전체 BLOCKED로 처리한다. 외국인 수급 필드는 거부한다.
- 입력에 선별 근거인 `FRESH_MARKET_SCAN`과 완전성 표시가 있어야 한다. 이전 추천 종목만 넣는 방식은 지원하지 않는다. 이 선언이 사실인지 검증할 실제 시장 수집기는 미구현이다.
- 정상 분석 결과는 CANDIDATES 또는 NO_TRADE. 자료 불량은 BLOCKED, 소스 오류는 FAILED, 제한 시간 초과는 TIMEOUT으로 구분한다. 늦은 결과·오래된 캐시를 최신 성공으로 대체하지 않는다.
- 테마·상관 그룹당 1개, 최종 0~3개. 가정 자금 기본 60만원, 최대 70만원이고 실제 계좌 잔액이 아니다. 비상 하한 기준 제안 계획손실 합계는 최대 1만원 안으로 수량을 제한한다. 비용·갭으로 실제 손실이 더 커질 수 있다. 체결이나 수익 보장은 없다.
- 점수와 제외 임계치는 **실험적 초기값**이다. 거래대금 100억원 미만, 지수 -2% 이하, 당일 +12% 이상, 5일선 괴리 8% 초과, 거래량 비율 1.2 미만 등을 보수적으로 제외한다. 비상 하한 기준 1차 목표 손익비 1.5 미만도 제외한다. 기존 매매 전략의 검증된 점수나 사용자 수익 확률로 부르지 않는다. PER·반도체 노출 세부 선호·배당형 전용 분석은 미구현이다.
- 손절/목표 구간과 호가단위 확인은 신뢰된 입력이 제공해야 한다. 원시 캔들로 자동 산출하는 수집 어댑터는 미구현이다. 현재 API는 주식 추천 표시용이며 실제 매수·매도·취소를 하지 않는다.
- 설명은 RULE_BASED이며 AI가 작성한 설명이 아니다. 호가·매도벽은 미연결 위험으로 표시한다. 입력 신뢰·유효기한·위험 한도 검증 전에는 실제 투자에 사용하지 않는다.
- 단일 프로세스 잠금과 메모리 캐시만 있다. 여러 AWS 인스턴스·Lambda 사이의 원자적 중복 차단·사용량 제한·비용 상한은 후속 작업이다.
- 자료 읽기·분석 마감은 협력적 deadline 검사다. 외부 수집기를 붙일 때는 외부 요청 자체의 timeout을 반드시 제한해야 한다. 브라우저 취소는 화면 대기만 중단하며 서버 계산이나 기존 매매를 취소하지 않는다.

## PC-C에서 먼저 할 일

1. 기존 규칙대로 AGENTS.md → PC-C 단독 인수인계 → 공동 인수인계 최신 기록 순서로 읽고 실제 Git 상태와 비교한다. 현재 모의운용 상태를 임의 변경하지 않는다.
2. 저장소 루트가 `C:\Test`인지 확인한다. 아래 명령은 CMD 기준이며 기존 앱의 `.venv` Python을 사용한다. 서버 실행과 테스트는 PC-C에서 진행한다.
3. 기존 전체 앱 회귀와 신규 테스트를 각각 실행한다. 이 코드는 운영 앱 밖이므로 기존 테스트 명령 하나만으로 신규 테스트까지 실행되는 것은 아니다.

```cmd
cd /d C:\Test
set "PYTHONPATH=C:\Test\stock-automation\src"
".venv\Scripts\python.exe" -m unittest discover -s stock-automation\tests -v
```

전체 앱 결과를 먼저 보존한 뒤, 다른 CMD 창에서 신규 개발분을 확인한다. PYTHONPATH는 해당 프로세스용이며 시스템 전역에 저장하지 않는다.

```cmd
cd /d C:\Test
set "PYTHONPATH=C:\Test\stock-automation\recommendation-lab"
".venv\Scripts\python.exe" -m unittest discover -s stock-automation\recommendation-lab\tests -v
node --check stock-automation\recommendation-lab\web\app.js
node --check docs\prototypes\recommendation-preview\dist\preview.js
node --test docs\prototypes\recommendation-preview\test-preview.cjs
node --test stock-automation\recommendation-lab\tests\web_client.test.cjs
```

Node가 없다면 설치하거나 JavaScript 검증을 미실시로 기록한다. Python 테스트만 통과했다고 화면·브라우저 검증까지 완료한 것으로 표시하지 않는다.

### 기본 차단 화면 확인

```cmd
cd /d C:\Test
".venv\Scripts\python.exe" stock-automation\recommendation-lab\server.py
```

브라우저로 `http://127.0.0.1:8765`를 연다. 추천 버튼을 누르면 **BLOCKED / DATA_SOURCE_NOT_CONNECTED**가 정상이다. 로그 출력에 계좌·키·입력 원본이 없어야 한다. Ctrl+C로 이 개발 서버만 종료한다. 운영 예약이나 서버 정지 명령을 실행하지 않는다.

### 가상 입력으로 화면 연결 확인

기존 `runtime` 안에 추천 개발분 전용 디렉터리를 만든다. 아래 파일명이 이미 있으면 삭제/덮어쓰기하지 말고 새 이름을 정해 모든 명령에 동일하게 사용한다. 가상 입력은 Git에 넣지 않는다.

```cmd
cd /d C:\Test
if not exist runtime\recommendation-lab mkdir runtime\recommendation-lab
".venv\Scripts\python.exe" stock-automation\recommendation-lab\sample_input.py --output runtime\recommendation-lab\fictional-01.json
".venv\Scripts\python.exe" stock-automation\recommendation-lab\server.py --snapshot runtime\recommendation-lab\fictional-01.json
```

입력 생성 후 90초 안에 버튼을 눌러 가상 후보를 확인한다. 이후 같은 파일을 쓰면 자료 만료로 차단되어야 한다. 실제 시세의 시각을 현재로 바꿔 신선하게 위장하지 않는다. 위 도구는 `is_sample=true`와 DEMO 종목만 생성하는 가상 입력 전용이다. 테스트 결과를 실제 추천 CSV에 넣지 않는다.

브라우저 체크 항목:

- [ ] 버튼을 누르기 전 네트워크 분석 요청이 없다.
- [ ] 가상 결과임이 명확하고 실제 계좌 잔액·체결로 보이지 않는다.
- [ ] 390px와 PC 폭에서 버튼·카드가 넘치지 않는다.
- [ ] 진행 중 중복 클릭이 차단되고 서버 쿨다운도 동작한다.
- [ ] 자료 만료 시 후보를 숨기며 오류가 NO_TRADE 성공으로 바뀌지 않는다.
- [ ] 화면 대기 취소가 기존 매매 중지로 표시되지 않는다.
- [ ] 네트워크 실패·느린 응답·오래된 결과·취소 후 늦은 응답을 확인했다.
- [ ] 개발 서버와 패키지에 계좌·API 키·로그·운영 지갑 데이터가 없다.

### 검토용 패키지 준비

집중 테스트·앱 회귀·수동 UI 검증을 통과한 뒤에만 새 이름으로 ZIP을 만들 수 있다. 이 명령은 배포하지 않는다.

```cmd
cd /d C:\Test
".venv\Scripts\python.exe" stock-automation\recommendation-lab\package_lab.py --output runtime\recommendation-lab\review-01.zip
```

manifest의 `deployment_ready=false`는 의도된 값이다. 파일 해시와 코드 목록을 검토하라는 뜻이지 배포 허용 플래그가 아니다. 검증했다고 이를 true로 수동 변경하지 않는다. 이 ZIP은 개발 localhost 서버용이며 AWS 런타임/인증/데이터 연결 구성까지 포함한 배포 패키지가 아니다.

## 아직 필요한 후속 개발

실제 버튼 추천을 운영 화면에서 쓰려면 다음을 별도 검토·구현·테스트해야 한다.

1. 분석 전용 읽기 수집기: 시장 새 스캔, 인증·호출 제한·현재 시각·거래소/세션·당일 수급·완성 분봉·뉴스 출처 검증. 기존 worker·자동 진입을 우회 호출하지 않는다.
2. 입력별 출처 증거와 호가단위·진입/손절/목표 자동 산출. 입력의 자체 검증 표시만으로 사실성을 인정하지 않는다.
3. 검증된 후보만 대상으로 하는 선택적 AI 설명. 허위 출처/숫자·비용·시간 상한을 서버에서 강제한다. AI가 없으면 RULE_BASED라고 표시한다.
4. Cognito/TLS와 별도 분석 API, 다중 인스턴스 요청 잠금·횟수 제한·독립 실행 자원. 기존 읽기 전용 대시보드 권한을 POST/주문 권한으로 넓히지 않는다.
5. 기존 단기 기동 AWS 구성과 충돌하지 않는 온디맨드 작업 방식 및 운영비 검토. 서버를 임의로 켜고 끄거나 기존 예약에 추천 작업을 끼워 넣지 않는다.
6. 실데이터 관찰과 성과 검증, 분리된 추천 기록, 사용자 승인 후 운영 메뉴·배포 연결. 과거/가상 결과로 실제 투자 성능을 보장하지 않는다.

현재 테스트 실행·수집기 실연동·AWS 통합이 남았으므로 “이제 배포만 하면 된다”고 보고하지 않는다. 실거래는 이 기능의 완료 조건이 아니다.

## PC-C 전달 프롬프트

> 최신 인수인계와 docs/프로그램 설계/버튼형_종목추천_PC-C_검증체크리스트.md를 읽어라. PC-D는 배포 전 개발 코드를 작성했지만 사용자의 지시로 테스트/서버 실행을 하지 않았다. 기존 운영 프로그램을 건드리지 말고 기존 전체 테스트와 신규 recommendation-lab 테스트, Node/수동 UI 검증을 각각 실행해 실제 결과를 기록해라. 실패했다고 안전장치를 약화하거나 입력 시각/검증 표시를 꾸미지 마라. 기존 AWS 예약·주문·지갑·원장·NXT 필터·실거래·kill switch는 유지해라. 배포와 실제 데이터/AI 연결을 임의로 완료 처리하지 말고 미완료 작업을 보고해라. 공동 인수인계10절 맨 위에 PC-C alias·변경 파일·실제 테스트 결과·남은 위험을 추가해라. 배포/commit/push는 별도 요청 없이 하지 마라.
