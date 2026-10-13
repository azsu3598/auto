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
