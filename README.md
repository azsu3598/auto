<div align="center">

# SABU Trading Console

### 키움증권과 AWS를 이용한 안전 우선 한국 주식 자동매매 시스템

종가배팅·중기·장중 단타를 서로 분리해 분석하고 기록하는 **모의운용 우선** 프로젝트입니다.  
수익 극대화보다 잘못된 주문과 큰 손실을 막는 것을 먼저 설계합니다.

[![Tests](https://img.shields.io/badge/PC--D_tests-175_pass_%7C_2_skip-16c79a?style=for-the-badge)](stock-automation/tests)
![Mode](https://img.shields.io/badge/mode-paper%20trading-2563eb?style=for-the-badge)
![Live](https://img.shields.io/badge/live%20trading-locked-f59e0b?style=for-the-badge)
![Kill Switch](https://img.shields.io/badge/kill%20switch-default%20ON-ef4444?style=for-the-badge)

</div>

![SABU Trading Console 데스크톱 화면](docs/assets/dashboard/stock-dashboard-desktop.png)

> [!IMPORTANT]
> 현재 운영 기준은 키움 **모의투자**입니다. 실거래는 비활성화되어 있고 비상정지는
> 기본 ON입니다. 실제 주문, 실계좌 Secret 연결, AWS 실거래 예약은 별도 승인과
> 통합검증 없이는 활성화하지 않습니다.

## 한눈에 보는 현재 상태

확인 기준: **2026-10-15 KST**, 소스 기준 `6ea16b0`. AWS 배포 상태는 **10월 14일
23:57 PC-C 인수인계** 기준이며 현재 AWS를 실시간 조회한 결과가 아닙니다.
현재 단계는 **고정 IP 네트워크 준비 완료 → 앱 배포·온라인 통합검증 대기**입니다.

| 전략과 기능 | 현재 상태 | 다음 확인 |
|---|---|---|
| KRX 종가배팅 | 엔진 구현 완료 | PC-C 키움 모의·AWS 통합검증 |
| 1~2개월 중기전략 | 엔진 구현 완료 | 실제 모의 데이터 검증 |
| 장중 단타 | 요청 시 단발 모의 스캔 | S3·DynamoDB·대시보드 연결검증 |
| 연속 단타 | 운영설계와 비용산정 완료 | 사용자 승인 후 별도 구현 |
| PC·모바일 대시보드 | 읽기 전용 UI 구현 완료 | Cognito·HTTPS 외부 배포 |
| 고정 IP 네트워크 | PC-C 기록상 생성·재기동 검증 완료, 서버 정지 | 실제 사설 Fargate 접속 경로·키움 허용 IP 확인 |
| AWS 앱 배포 | 최신 ECR 이미지 준비, 앱 스택 미배포 | 예약 비활성 배포·S3/DynamoDB/API/알림 검증 |
| 컨테이너 보안 | 격리·임시 폴더 권한 보완, PC-C Docker 검사 통과 기록 | 실제 Fargate 실행·최신 취약점 재검사 |
| 실거래 | 안전 잠금 | 모든 안전 관문 완료 후 별도 승인 |

> [!WARNING]
> 2026-10-14 검토 자료에는 **미해결 고유 CVE 69개(High 14개)**가 남아 있습니다.
> 비루트·읽기 전용 파일시스템·권한 제거는 노출을 줄이는 조치이며 취약점 패치 완료를
> 뜻하지 않습니다. 모의 통합검증도 [보안 검토의 재검증 조건](docs/%EC%9A%B4%EC%98%81%20%EA%B2%80%EC%A6%9D/2026-10-14_Docker_%EC%B7%A8%EC%95%BD%EC%A0%90_PC-D_%EA%B2%80%ED%86%A0.md)을 따라 진행합니다.

## 프로젝트 진행도

![진행 현황: 5개 관문 중 핵심 구현·로컬 검증 완료, PC-C 통합검증 진행, 5거래일 모의운용 대기, 실거래 잠금](docs/assets/dashboard/project-progress.svg)

**완료 2 · 진행 1 · 대기 1 · 잠금 1** — 코드량이 아닌 5개 관문의 상태입니다.
운영 준비율이나 수익률·실거래 안전성의 백분율이 아닙니다. 그래프는 자동 연동된
모니터링 화면이 아니라 아래 검증 기록을 반영한 정적 요약입니다.

| 안전 관문 | 상태 | 완료 기준 |
|---|---|---|
| 핵심 구현 | **완료** | 전략 분리, 위험관리, 원장, 대시보드와 주문 안전 골격 |
| 로컬 검증 | **완료** | PC-D 전체 177개 중 175개 통과·Docker 2개 skip, `compileall` 통과 |
| PC-C 통합검증 | **진행 단계** | Docker 포함 177개 통과 기록, 실제 Fargate·API·저장·알림 검증은 미완료 |
| AWS 모의운용 | **대기** | 예약 실행과 5거래일 이상 무사고 모의운용 |
| 실거래 | **잠금** | 계좌 보호·체결 대사·장애 복구 검증과 사용자 별도 승인 |

PC-C에서는 `/tmp` 권한을 보완한 이미지를 빌드·검사하고 ECR에 반영한 기록이 있습니다.
고정 IP 중계 서버도 생성·재기동 검증 후 정지했습니다. 하지만 **실제 Fargate 앱 스택은
미배포, 모든 예약은 비활성** 상태로 인수인계됐습니다. 테스트 성공과 운영 성공은 다릅니다.

현재 앱은 **AI 모의체결을 자체 원장에 기록**합니다. 키움 증권사에 모의 주문을 제출하거나
실제 주문을 실행하는 기능이 운영 중이라는 뜻이 아닙니다.

### 예약을 켜기 전 확인할 4가지

1. 앱 재전송·실행 제한과 NAT 종료 시각 정합성: 09:10 작업의 1시간 재전송 허용과 09:25 정지 충돌.
2. 네트워크 준비·작업 종료 확인: 준비 지연이나 실행 중 작업을 정해진 시간만으로 처리하지 않기.
3. 로컬·원격 UserData 차이 관리: 설치 제한 로컬 600초와 원격 60초를 다음 갱신 전 검토.
4. 실제 앱 통합검증과 보안: Fargate·키움·저장·알림 및 최신 이미지 취약점 검사.

구체적인 테스트와 완료 기준은 [PC-C 최신 보완 체크리스트](PC-C_단독진행_전체인수인계.md)를
따릅니다. 확인 전에는 모의 예약도 켜지 않으며 실거래는 계속 잠금 상태를 유지합니다.

## 세 가지 독립 전략

| 전략 | 판단 시점 | 기본 보유기간 | 핵심 원칙 |
|---|---|---|---|
| **종가배팅** | KRX 15:20 | 다음 거래일 09:10까지 | NXT 종목 제외, 약한 시장에서는 `NO_TRADE` |
| **중기전략** | 장 마감 신호 후 다음 날 확인 | 20~40거래일 | 공시·재무 위험 확인, 종가를 체결가로 소급하지 않음 |
| **장중 단타** | 요청 시 09:10~14:50 | 당일 15:10까지 | 단발 모의 스캔, 연속 감시와 실주문은 미연결 |

세 전략은 자금, 점수, 포지션, 손절, 성과와 원장을 공유하지 않습니다. 추천할 만한
종목이 없을 때는 거래하지 않는 것이 정상 결과입니다.

## 시스템 구조

아래는 목표 연결 구조입니다. 고정 IP용 NAT 네트워크까지 준비됐다는 기록이 있으며,
앱의 실제 사설망 접속·API·저장소 연결은 아직 통합검증 전입니다.

```mermaid
flowchart LR
    K[키움 모의 API] --> W[AWS 예약 작업]
    D[OpenDART와 촉매 자료] --> W
    W --> S{전략 라우터}
    S --> C[종가배팅]
    S --> M[중기전략]
    S --> T[단타]
    C --> DB[(DynamoDB)]
    M --> DB
    T --> DB
    C --> B[(S3 원본 보관)]
    M --> B
    T --> B
    DB --> UI[SABU Trading Console]
    DB --> N[텔레그램 알림]
    L[실주문 경로] -. 안전 잠금 .-> S
```

현재 AWS 구조는 정해진 시간에 짧게 실행되는 Fargate 작업과 예약형 고정 IP 중계 서버를
기본으로 합니다. 현재 중계 서버는 연속 단타 실행용이 아닙니다. 장중 연속 단타는 별도
승인·구현 범위이며 상시 감시 코드나 인프라를 배포하지 않았습니다.

## 핵심 안전장치

- `LIVE_ORDER_ENABLED` 기본 비활성화와 비상정지 기본 ON
- NXT 가능 종목의 KRX 종가배팅 강제 제외
- 데이터 지연, API 오류와 세션 불일치 시 안전 종료
- `IMMEDIATE`와 `5M_CONFIRMED` 손절, 별도 비상 하드 스톱
- DynamoDB 원자적 지갑 차감과 동일 결정 중복 실행 방지
- 계좌 지문과 최초 보유수량 기준선을 이용한 기존 보유종목 보호
- 프로그램의 확인된 실제 체결수량까지만 매도 허용
- 부분체결·취소·거부·불명확 상태 분리와 잔고 불일치 시 비상정지
- 모의·실거래 및 종가배팅·중기·단타의 자금과 성과 완전 분리

## 대시보드

**2026-10-19 사용자 요청으로 AWS 웹 화면을 일시 중지했습니다.** 접속하면 중지 안내만
표시되며 새 화면에서 로그인·자동 원장 조회를 실행하지 않습니다. 웹 구성과 계정은
보관하고 모의매매 운영을 시작할 때 재개합니다. 이 조치는 AWS 자원 삭제가 아닙니다.

`SABU Trading Console`은 주문 화면이 아니라 **읽기 전용 운영 화면**입니다. 가용현금,
투자원금, 누적손익, 열린 포지션, 판단 이유, 전략별 지갑, 일별 총자산 추이와 안전장치
상태를 PC와 모바일에서 확인할 수 있습니다.

2026-10-19 PC-C에서는 별도 AWS 모바일 웹 스택 생성과 파일 업로드를 확인했습니다.
CloudFront HTTPS·Cognito 로그인·모의 원장 읽기 API로 구성하며, HTTPS·비로그인
차단 검사를 통과했습니다. 사용자가 로그인 후 원장 숫자 표시까지 확인했습니다.
PC가 꺼져도 사용할 수 있는
구성이지만 매매 예약 활성화와는 별개입니다. 현재 매매 예약은 꺼져 있습니다.
이 결과는 위의 10월 15일 기준 현황보다 최신이며, 세부 결과와 남은 작업은
[공동 인수인계](Codex_세션간_공동_인수인계.md)의 최신 기록을 따릅니다.

<details>
<summary><strong>모바일 화면 보기</strong></summary>

<p align="center">
  <img src="docs/assets/dashboard/stock-dashboard-mobile-500.png" width="360" alt="SABU Trading Console 모바일 화면">
</p>

</details>

## 로컬에서 화면 실행

<details>
<summary><strong>Windows PowerShell 실행 명령 보기</strong></summary>

```powershell
Set-Location C:\Test\stock-automation
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m stock_automation.cli dashboard --fixture examples/dashboard_fixture.json
```

브라우저에서 `http://127.0.0.1:8765`를 엽니다. 샘플 데이터 화면은 읽기 전용이며
주문을 제출하지 않습니다.

</details>

<details>
<summary><strong>Docker 빌드 명령 보기</strong></summary>

```powershell
Set-Location C:\Test
docker build -f stock-automation\Dockerfile -t stock-automation:dev .
```

Docker 빌드 컨텍스트는 저장소 루트입니다. `stock-automation`과
`Kiwoom-REST-API`는 형제 폴더로 유지합니다.

</details>

## PC별 작업 구분

| 환경 | 기본 경로 | 역할 |
|---|---|---|
| PC-D | `D:/Test` | 코드, 설계, 리뷰, 문서와 인수인계 |
| PC-C | `C:/Test` | Docker, 키움 모의, DynamoDB와 AWS 통합검증 |

PC-C는 pull 후 `AGENTS.md`, PC-C 전체 인수인계, 공동 인수인계와 실제 코드를 비교하고
전체 테스트부터 다시 수행합니다. 비밀키, 토큰, 계좌번호와 AWS 자격증명은 코드,
Markdown, Git과 일반 로그에 기록하지 않습니다.

## 폴더 안내

```text
<WORKSPACE>/
├─ stock-automation/        자동매매 코드·테스트·AWS 템플릿
├─ Kiwoom-REST-API/         키움 연동 라이브러리
├─ docs/                   분석·설계·운영 검증 문서
│  └─ assets/dashboard/    대시보드 화면 이미지
├─ Sabu/                   차트 학습 자료
│  └─ 교재/                정규 교재와 Notion 가져오기 파일
├─ reference/              기존 기준 자료와 거래기록
└─ archives/               로컬 복구 백업·옛 전달물, Git 제외
```

이 프로젝트에서 새로 작성하는 Markdown은 모두 현재 저장소 안에 둡니다. 일반 문서는
`docs/`, 차트 공부 자료는 `Sabu/`에 저장하며, 필수 인수인계와 기존 실행 가이드는
루트 경로를 유지합니다. 실행 코드가 참조하는 두 프로젝트의 형제 폴더 관계도 유지합니다.

`GorapaduckPet`은 이 워크스페이스에서 제거했습니다. 복구용 압축본과 관련 솔루션,
예전 전달 ZIP·보조 스크립트는 로컬 `archives/`에 보관하며 새 Git 전달에 포함하지 않습니다.

## 다음 작업

- [x] PC-C 모의용 Secret과 권한 보완 이미지의 ECR 반영 기록 확인
- [x] 고정 IP NAT 네트워크 생성·재기동 검증 후 정지 기록 확인
- [x] 비루트·read-only·권한 제거·임시 폴더 권한 보완과 회귀 테스트
- [x] PC-D 175개 통과·Docker 2개 skip, PC-C Docker 포함 177개 통과 기록 구분
- [ ] PC-C pull 후 세 인수인계·실제 Git/코드·전체 테스트 재확인
- [ ] 재전송/종료 시각, 준비/종료 연동, UserData 차이 검토와 회귀검사
- [ ] 키움 모의 허용 IP·앱 배포 IAM·수수료/세금·전체 휴장일 확인
- [ ] 앱 스택을 예약 비활성 상태로 배포
- [ ] 실제 사설 Fargate egress/EIP·임시 폴더·키움/OpenDART 읽기 진단
- [ ] CloudWatch·S3·DynamoDB·텔레그램 통합검증 및 이미지 취약점 재검사
- [ ] 핵심 모의예약 활성화 후 5거래일 이상 관찰
- [ ] Cognito·HTTPS 기반 모바일 외부 접속
- [ ] 실거래 안전 기능의 실제 계좌 환경 검증
- [ ] 모든 관문 통과 후에만 실거래 전환 여부 별도 결정

## 문서

- [자동매매 엔진 상세 설명](stock-automation/README.md)
- [사부의 차트 공부방과 정규 교재](Sabu/README.md)
- [PC-C 단독 진행 전체 인수인계](PC-C_%EB%8B%A8%EB%8F%85%EC%A7%84%ED%96%89_%EC%A0%84%EC%B2%B4%EC%9D%B8%EC%88%98%EC%9D%B8%EA%B3%84.md)
- [AWS 자동매매 실행 가이드](AWS_%EC%9E%90%EB%8F%99%EB%A7%A4%EB%A7%A4_%EC%8B%A4%ED%96%89%EA%B0%80%EC%9D%B4%EB%93%9C.md)
- [세션 간 공동 인수인계](Codex_%EC%84%B8%EC%85%98%EA%B0%84_%EA%B3%B5%EB%8F%99_%EC%9D%B8%EC%88%98%EC%9D%B8%EA%B3%84.md)
- [고정 IP 모의배포와 실제 검증 상태](stock-automation/infra/고정IP_모의배포_진행.md)
- [Docker 취약점 검토와 PC-C 재검증 조건](docs/%EC%9A%B4%EC%98%81%20%EA%B2%80%EC%A6%9D/2026-10-14_Docker_%EC%B7%A8%EC%95%BD%EC%A0%90_PC-D_%EA%B2%80%ED%86%A0.md)
- [AWS 프로그램 아키텍처](docs/%ED%94%84%EB%A1%9C%EA%B7%B8%EB%9E%A8%20%EC%84%A4%EA%B3%84/AWS_%ED%94%84%EB%A1%9C%EA%B7%B8%EB%9E%A8_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98.md)
- [연속 단타 AWS 운영설계와 예상비용](docs/%ED%94%84%EB%A1%9C%EA%B7%B8%EB%9E%A8%20%EC%84%A4%EA%B3%84/%EC%97%B0%EC%86%8D_%EB%8B%A8%ED%83%80_AWS_%EC%9A%B4%EC%98%81%EC%84%A4%EA%B3%84_%EB%B0%8F_%EC%98%88%EC%83%81%EB%B9%84%EC%9A%A9.md)

## 투자 유의사항

이 프로젝트의 분석과 모의매매 결과는 수익을 보장하지 않습니다. 실제 투자 판단과
손실 책임은 사용자에게 있으며 충분한 모의운용과 장애·손실 시나리오 검증 없이
실거래로 전환하지 않습니다.
