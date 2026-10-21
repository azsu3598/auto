# 고정 IP를 사용하는 AWS 모의운용 배포

## 2026-10-21 PC-C 최신 — 10월22일 PC OFF 재검증 ARMED_IN_AWS

관리자 업데이트 실제 소스/권한/매개변수/진단 정의를 대조한 뒤 새 고유 시험 표식을 생성하고 시험용4개만 켰다. 최종 별도 재조회4/4 일치, 현재 NAT stopped·클러스터0·옛 FAILED/영구 lease 보존을 확인했다. **10/22 KST 08:55 기동→09:02 준비→실제09:05 빈 청산 검증→09:16 감시→09:20 독립정지**이며 PC OFF로 진행된다. 일반 모의매매/오후 pilot/모바일은 아직 비활성이다. 결과는 아직 미래이고 ARMED를 PASSED로 표시하지 않는다.

결과 읽기는 Git 제외 `runtime/check_worker_retest_20261022.py`를 사용한다. 원문/실제 식별자는 `runtime/paper-worker-retest-armed-20261021.json`과 `paper-worker-retest-final-read-20261021.json`에만 보관한다. CFN VerificationState DISABLED와 SDK 시험4개ENABLED는 의도된 차이이므로 실행 전 기본 업데이트로 끄지 않는다. 최신 전체327개/skip0·focused28·Node4·9템플릿/업로드파일 lint·AWS ValidateTemplate 통과, LIVE0·실주문 없음 유지.


## 2026-10-21 20:26 PC-C 장외 실제 검사 완료 — 15+23항목·정리/정지 PASSED

현재 시각에 단발 Fargate 진단2개를 실행해 온라인 doctor15개(키움 demo·OpenDART·고정 IP·격리 저장소·텔레그램)와 격리 지갑/lease 계약23개를 통과했다. 수정된 시험 정리 구현을 PC 작업 계정에서 실행해 실제 목록 조회·동일 부팅 소유 확인·제어 종료·NAT stopped와 클러스터0도 통과했다. 기존 원장은 네트워크 제어 기록 외 불변이다. 결과는 Git 제외 runtime/paper-after-hours-smoke-20261021.json에 보관한다. 장중 거래 phase나 Lambda 역할의 전체 RUN/WATCH 검증을 대신하지 않으며 오전 FAILED는 보존했다. 일반 모의매매/오후 pilot/모바일은 이번에 켜지 않았다.


## 2026-10-21 PC-C 반영 완료 — 권한/소스14항목 대조·시험 예약4개 OFF

관리자 업데이트 UPDATE_COMPLETE 후 실제 Lambda 소스·정의 불변·작업 목록 조회 성공·서버 stopped/작업0·원래 FAILED 및 완료 lease 보존을14/14 대조했다. CFN의 기본 DISABLED가 같으면 기존 SDK drift가 남아, 종료된 시험4개만 실제 OFF로 정리하고 재조회했다. 원래 FAILED를 PASSED로 바꾸거나 앱을 재실행하지 않았다. 정기 매매 예약은 CFN 설정상 OFF이며 이번에 활성화하지 않았다. 실제 정기 예약 직접 읽기는 작업 계정 권한 제한이 있어 상태 조회 성공으로 확대하지 않는다. 새 정상 시간 재검증은 남아 있고 오후 pilot/모바일 재개는 미진행이다.


## 2026-10-21 PC-C 최신 상태 — 오전 worker 정상·정리 권한 수정 대기

- 오전 실제09:05 빈 청산 worker·완료 lease·원장 불변 검사는 통과했으나 종료 정리 확인 실패로 전체 시험은 FAILED다. 기존 결과는 보존하며 PASSED로 바꾸지 않는다. 현재 읽기 확인은 NAT stopped·ECS running/pending0·정기 모의 예약 OFF다. 오후 모의 pilot은 미배포다.
- 시험의 ListTasks Resource 지정 오류를 정확한 클러스터/서울 조건 읽기로 수정했다. 원래 worker 이유와 비밀 없는 AWS 오류 코드/호출 이름을 보존하고, 목록 조회 실패에도 소유가 검증된 기존 부팅의 종료 경로를 시도하되 정리 미확인은 FAILED로 유지한다. 새 주문/실거래 권한은 없다.
- 로컬 focused24·전체323/skip0·Node4·9템플릿 lint/구문·AWS ValidateTemplate 통과. 관리자 반영 파일은 Git 제외 `runtime/paper-worker-cleanup-fix-console-20261021.yaml`, 대상은 기존 `stock-automation-paper-worker-test`다. 기본 VerificationState DISABLED 유지, 새 시험/예약 활성화 없음. 반영 후 실제 권한과 원래 FAILED 불변·서버/정기 예약 OFF를 재조회해야 한다.


NAT 네트워크와 예약 비활성 앱 배포를 마쳤으며 실제 Fargate 통합검증을 진행 중이다. 사용자는 2026-10-14 전체
예상 월 $7~10(세금·크레딧 제외)으로 중계 EC2 1대와 고정 IP 1개를 추가하는 방향을
승인했다. 최초 시작·정지·앱 예약은 모두 꺼 둔다. 실거래와 실계좌 Secret 연결은 금지다.

## 2026-10-20 저장소23항목 통과·PC OFF 정상 시간 검증 준비

`storage_contracts.py`와 명시적 확인이 필요한 CLI를 추가해 고유
CONTROL#INTEGRATION_PROBE 키에서 실제 DynamoDB 지갑·실행 잠금 계약을 검증했다.
첫 실제 검증에서 `owner` 예약어 때문에 기존 실행 완료 처리 조건식이 거부되는
문제를 발견했다. #owner 별칭으로 수정했으며 소유자 일치·RUNNING 조건은 유지한다.
수정 후 실제23항목을 통과했고 시험 레코드 삭제·원래 원장 불변·정상 제어 종료와
NAT stopped를 확인했다. 실제 모의 체결은 생성하지 않았다.

현재 앱 이미지는 Git 제외 `runtime/ecr-storage-ownerfix-plain-20261020-result.json`의
검증된 digest다. 기존 기반 레이어/권한/패키지와 설정은 유지하고 CLI·격리 검증·
runtime_safety 소스만 반영했다. 소스/설치40파일 일치, ECR push0·digest 재다운로드를
검증했다. 오프라인10/18 DB의 취약점203조합/94고유 결과는 기존과 동일하다.
Docker500·OCI index 전송 실패·수정 전 저장소 실패 원문도 runtime에 보존한다.

사용자는10/21 오전 PC를 꺼둬야 하므로 별도 AWS 일회성 정상 시간 시험을 선택했다.
`paper_worker_verifier.py`, `paper_worker_bootstrap.py`, 생성 도구와
`paper-worker-verification.yaml`을 준비했다. 운영 이미지와 안전 설정/모의 Secret
참조가 같은 별도 진단용 작업 정의이며 새 EC2/IP/서비스를 만들지 않는다. 컨테이너를
미리 준비하고 실제09:05가 된 뒤 원래 run_bounded와 aws_runtime을 실행한다. 시각을
조작하거나 허용 창을 늘리지 않는다. 시험 전 원장이 기준선과 다르거나 지갑/포지션/
미전송 알림이 있으면 실행하지 않는다. 코드상 실행 단계는 빈 EXIT_0905로 고정된다.

10/21 KST 계획은 **08:55 기존 NAT 기동 → 09:02 컨테이너 준비 → 실제09:05 실행 →
09:16 누락·실패 감시 → 09:20 독립 API 정지**다. 정상 결과도 작업/서버 정리를 확인한
후에만 통과로 기록하고 Telegram에 결과를 보낸다. 실행 시도 완료와 원장 불변을 실제
로그·DynamoDB·ECS에서 대조한다. 진입·전략 시세 수집/체결이나 미래5일 성과 검증을
대신하지 않으며 **정기 모의매매 예약은 켜지 않는다**.

최신 후속: 관리자 생성 후 **CREATE_COMPLETE와 실제 배포 대조를 마치고 ARMED_IN_AWS**다.
실제 Lambda ZIP/index.py·900초/128MiB/동시1, 전체 템플릿/매개변수, 진단용/운영
작업 설정과 모의 Secret 참조·bootstrap 원문·네 예약의 시각/대상/역할을 대조했다.
S3 ARMED 표식을 쓰고 읽기 일치를 확인한 뒤 독립 정지→감시→실행→기동 순서로
시험용4개만 ENABLED로 바꿨다. 별도 재조회에서도4개와 대상/표현식 일치를 확인했다.
현재 NAT stopped·앱 Core/NXT/제어 정기 예약 OFF, 미래 시험 결과는 ARMED다.
이 시점부터 PC가 꺼져도 내일 시험은 AWS에서 수행된다. 실제 시험 PASSED는 아직
미확인이고 정기 모의매매나 모바일 웹은 활성화하지 않았다.

관리자 업로드 파일은
Git 제외 `runtime/paper-worker-console-20261020.yaml`이며 모든 시험 예약 기본값은
DISABLED다. 생성 후 작업 계정으로 위 시험 예약4개만 켠 상태다. arming 도구는
`runtime/arm_worker_verification_20261020.py`이며 기존 결과/표식을
덮어쓰지 않는다. 정기 매매 예약과 모바일 웹은 계속 꺼 둔다.

전체301개/skip0(기존 이미지의 실제 Docker2개 포함), Node 인증4개, 인프라8개
템플릿 lint·안전 검사, 구문과 AWS ValidateTemplate을 통과했다. 관리자 생성 후 실제
배포 대조도 통과했으며 내일의 미래 결과는 미확인이다. 시험용 예약을 작업 계정으로 켠 뒤에는
CFN 기본 VerificationState=DISABLED와 실제 ENABLED가 다를 수 있으며 의도된
시험 예약 활성화다. 운영 스택의 Core/NXT/제어 스케줄 상태와 혼동하지 않는다.
증거는 Git 제외 `runtime/paper-worker-armed-20261020.json`, 다음 읽기 전용 도구는
`runtime/check_worker_verification_20261021.py`다. 정상 시도 기록은 삭제/재획득하지
않는다. 이후 다른 부팅을 한 경우 이전 시험의 LaunchTime과 현재 서버를 혼동하지 않는다.

## 2026-10-20 실제 120분 자동정지 시험 통과 확인

사용자가 PASSED 텔레그램 수신을 보고했다. AWS 작업용 재인증 후 S3의 최종 시험
증거와 실제 EC2 상태를 읽기 전용으로 대조해 **13항목 모두 통과**했다. 같은 시험/
서버/LaunchTime, 7200초 타이머 활성, 정지 이벤트 시간과 ARMED 이후 순서,
OS 종료 사유 `Client.InstanceInitiatedShutdown`, 현재 stopped를 확인했다.
실제 부팅부터 정지 이벤트까지 **7263초(121분 3초)**로 승인된 120~125분 창에 든다.
사용자 PC가 꺼진 동안 AWS가 수행한 결과이며 이번에 타이머를 다시 실행하지 않았다.

앱 Core/NXT 및 제어 스택의 매매 예약 매개변수는 모두 DISABLED다. 모바일 웹의
일시 중지 상태도 이번 작업에서 변경하지 않았다. 이 결과로 자동 모의매매를 켜거나
앱 전체 검증이 완료됐다고 선언하지 않는다. 다음은 실제 허용 실행 시간의 앱 가드·
전략별 지갑/원장 검증 및 모의 예약 활성화 관문이다. 시험 스택·관찰 규칙·일회성 예약
메타데이터의 후속 정리는 아직 별도 남아 있다.

증거는 Git 제외 `runtime/paper-timer-final-verification-20261020.json`, 읽기 도구는
`runtime/verify_timer_result_20261020.py`다. 앱/인프라 코드 변경 없이 실제 결과를
대조했고 이전 전체272개/skip0·Node4개 결과를 유지한다. 실주문·실계좌 Secret·
kill switch 해제·거래 예약 활성화 없음.

## 2026-10-19 모바일 읽기 전용 웹 배포

최신 사용자 지시: 모의매매 운영 전까지 모바일 웹을 일시 중지한다. 원본 정적 파일
세 개를 해시 대조해 Git 제외 runtime에 백업하고, index.html은 로그인·조회 없는
중지 안내, app.js/auth.js는 조회하지 않는 코드로 교체한다. 기반 Cognito/API/S3/
CloudFront는 삭제하지 않는다. 기존 열린 탭은 닫고, 재개 시 백업과 게시 manifest를
대조해 복구·캐시 무효화·HTTPS·사용자 인증 조회를 재검증한다. 이 조치로 기본 저장
등의 비용이 0이 되었다고 표시하지 않는다.

사용자 모바일 접속 요청에 따라 별도 `stock-automation-paper-web` 스택 생성을
확인하고 검토한 정적 파일을 업로드했다. 비공개 S3·CloudFront HTTPS·Cognito LITE
관리자 생성 사용자·JWT HTTP API·128MiB 조회 Lambda로 구성한다. API는 모의
테이블 Scan과 자체 로그만 허용하고 Secret·주문·원장 쓰기 권한을 갖지 않는다.
기존 EC2·고정 IP·앱 이미지·매매 예약을 바꾸지 않는다.

프런트는 Authorization Code/PKCE를 사용하고 접근 토큰을 메모리에만 둔다.
실거래 레코드는 응답에서 제외한다. 공개 회원가입·SMS·이메일 초대는 사용하지 않는다.
예약표는 예정 시간 표시이며 실제 예약 활성 여부를 나타내지 않는다.

Python 전체272개/skip0, Node 인증4개, 인프라 템플릿7개 lint·안전 검사,
AWS ValidateTemplate과 API ZIP 원문 일치 검증을 통과했다. 모바일390×844 로그인
화면도 확인했다. 전체 검사 첫 실행의 Docker500은 정상 재시작 뒤 재검사해 통과했다.
실제 배포 API ZIP의 해시와 세 모듈 원문, 전체 스택 템플릿/매개변수, Cognito
관리자 전용 생성·LITE·공개 클라이언트 설정, CloudFront Deployed를 확인했다.
업로드 파일은 S3 읽기와 HTTPS 전송 결과가 원본 바이트와 일치한다. HTTPS 보안 헤더와
브라우저 no-store, 비로그인·가짜 토큰 API 401, 직접 S3 403, 로그인 페이지200 검사를
통과했다. 이후 사용자가 로그인 후 원장 숫자 표시를 확인했다. 최근 조회 함수 로그의
실행 완료1건·런타임 오류 표식0건도 대조했다. 휴대폰 기기 직접 접속 여부는 아직
확인하지 않았으며 웹 접속 확인만으로 자동 모의매매 준비 완료를 선언하지 않는다.

관리자 업로드 파일·실제 자원 식별자·배포 증거는 Git 제외 runtime에 보관한다.
120분 시험은 별도로 진행 중이며 원래 타이머와 거래 예약 OFF를 유지한다.

## 2026-10-19 PC 종료 후 일회성 타이머 시험 준비

최신 결과: 관리자 재업데이트 후 실제 스택/전체 매개변수·ZIP 소스·정지 감시 대상과
두 예약 검증을 통과했다. **현재 시험은 AWS에서 ARMED_IN_AWS로 진행 중**이다.
기동별 전달 준비와 SSM의 boot epoch·원래120분 타이머/정지 서비스 검사를 통과하고
현재 LaunchTime에 묶인 ARMED 표식을 실제 S3에 저장·읽기 대조했다.
예상 OS 정지는 **10/19 21:55:21 KST**, 결과 확인22:07, 별도 정지22:17이다.
PC 종료와 관계없이 AWS가 수행하며 최종 통과 여부와 알림 전달은 아직 미래 결과다.
현재 NAT가 시험 목적으로 running인 것은 의도된 상태다. 앱 작업0·거래 예약 OFF를
유지한다. 이를 자동 모의매수 활성화나120분 성공 결과로 표시하지 않는다.

후속: 시험 스택 CREATE_COMPLETE를 확인했다. GetTemplate의 inline 코드 한글은 `?`로
조회됐지만 실제 Lambda ZIP을 내려받아 해시와 index.py 원문이 원본과 일치함을 확인했다.
arming 도구는 실제 ZIP을 먼저 검증하고 해당 코드 필드만 그 원문으로 대조하며,
나머지 전체 템플릿 필드는 엄격히 비교한다. 실제 배포 코드가 다르면 진행하지 않는다.

첫 기동 전 시험 표식 PutObject는 작업 계정 권한 부족으로 거부됐다. 서버 기동 전의
실패이며 시험은 아직 시작하지 않았다. OperatorReviewPolicy에 이 시험 객체 하나의
PutObject만 추가했고 전체259개/skip0·인프라 검사를 통과했다. 관리자 시험 스택 업데이트를
요청했으며 매개변수 CheckAt/FailSafeAt도 UTC13:07/13:17(한국22:07/22:17)로 갱신한다.
업데이트 완료와 유효한 기동 시각 확인 전에는 이전 계획으로 서버를 시작하지 않는다.

사용자가 한 시간 뒤 PC를 꺼야 한다고 확인했다. 120분 설정을 단축하지 않고 시험을
AWS에 남기는 별도 구성을 준비했다. 현재는 **관리자 시험 스택 생성 대기**이며 시험을
시작하거나 모의매수 예약을 켠 상태가 아니다. 날짜가 바뀌어 다음 실행 목표일은 10/20이다.

`paper_timer_verifier.py`와 `build_timer_verification_template.py`가 만드는
`paper-timer-verification.yaml`은 기존 NAT의 정지 이벤트만 관찰하는 Lambda, 제한 IAM,
로그, 일회성 결과 확인/별도 정지 예약으로 구성된다. 서버/IP/증권사 주문/거래 예약 변경
권한은 없다. 결과 객체 한 개와 텔레그램 Secret만 사용하며 함수는 128MiB·최대60초·동시1이다.
원본 제어 함수나 앱 이미지를 바꾸지 않는다.

시험 준비 표식의 boot/LaunchTime·120분 설정을 확인하고, 실제 EC2 STOPPED 이벤트의
시각과 OS 종료 사유를 대조한다. API 정지, 조기 정지, 다른 기동, 이벤트 미수신을
성공으로 계산하지 않는다. 실패 시 동일 서버의 정리를 먼저 시도하고 결과/알림을
남긴다. 감시 함수가 실패하는 경우를 위한 별도 일회성 StopInstances도 둔다.
EC2 사유 구분은 [AWS StateReason](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_StateReason.html),
이벤트 형식은 [EC2 상태 변경 이벤트](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-instance-state-changes.html)를 따른다.
이 판정은 이벤트·부팅 정보에 근거하며 서비스 journal의 실행 증거까지 확보한 것은 아니다.

CloudFormation은 이 리소스의 ActionAfterCompletion을 지원하지 않아 사용하지 않는다.
두 예약은 at 표현식으로 한 번 실행되며 완료 후 시험 스택/관찰 규칙 정리는 후속 작업이다.
기존 앱/NAT/제어 거래 예약은 DISABLED다. 2시간 결과가 나오기 전에 완료로 표시하거나
내일 자동 모의매수가 확정됐다고 안내하지 않는다. 정상 시간의 앱 전체 실행 가드와
전략별 지갑/원장 검증도 별도 남아 있다.

로컬 신규9개를 포함한 전체258개/skip0, 여섯 템플릿 lint·안전 검사,
AWS ValidateTemplate, Python 구문 검사를 통과했다. 중간의 미지원 CFN 속성과 로컬
Docker500 오류는 수정/정상 재시작 후 재검사했으며 실패 로그도 runtime에 남긴다.
관리자용 `runtime/paper-timer-console-20261019.yaml`과 시간/식별자 포함 계획은 Git 제외다.
생성 완료 후 `runtime/arm_aws_timer_trial_20261019.py`가 실제 함수 ZIP·템플릿·감시 대상과
정리 예약을 확인하고, 제한 시각 안에서만 기동·부팅/타이머 검사·시험 표식 등록을 한다.
이 단계가 성공하기 전에는 PC를 꺼도 시험이 계속된다고 확정하지 않는다.

## 2026-10-18 네트워크 설정 일치·재기동 검증 완료

관리자 네트워크 IAM 업데이트 후 UPDATE_COMPLETE와 최신 소스 일치를 실제 조회했다.
검토한 UserData 단독 변경 세트를 실행해 네트워크 UPDATE_COMPLETE를 확인했다.
CloudFormation 자원 15개의 물리 식별자와 출력이 모두 유지됐으며 서버·고정 IP를
교체하지 않았다. 원격 전체 템플릿과 로컬 소스, 실제 EC2 UserData까지 일치한다.
이전 설치 제한 60초와 소스 600초/2회 차이는 이제 해소됐다.

갱신 뒤 제어 함수로 다시 기동해 현재 부팅의 전달 규칙·독립 타이머와 READY 증명을
확인했다. 같은 시작 요청의 중복 거부, 새 이미지 사설 doctor 15항목/exit0, 작업 없는
정상 제어 종료를 통과했고 NAT stopped를 확인했다. 실행 예약은 계속 꺼 둔다.
사용자는 앞선 시험의 텔레그램 알림 3개 수신을 보고했다. 개별 알림 종류/횟수의 대응이나
이번 추가 doctor 알림의 사람 수신까지 별도 확인한 것으로 확대하지 않는다.

사용자가 **120분 타이머의 실제 만료 정지 시험은 다음에 진행**하도록 선택했다.
이번에는 타이머 활성·설정만 재확인했고 2시간 만료를 기다리거나 완료로 표시하지 않았다.
다음 재개 시 해당 시험과 정상 거래일의 앱 실행 잠금·전략별 원장/지갑 및 미래 5거래일
검증을 진행한다. 자동 예약·NXT·실거래와 kill switch는 변경하지 않았다.
새 코드 수정 없이 기존 전체249개/skip0 결과를 유지하며 실제 인프라 갱신/재기동 증거를
추가했다. 원문은 Git 제외 runtime, 공통 인수인계는 최신 기록을 참조한다.

## 2026-10-18 제어 함수 배포 후 실제 검증

아래 이전 경과보다 이 결과가 우선한다. 관리자 보고 계정 Lambda 한도/미예약 한도는
각각 400이며, 예약 동시 실행 2개를 유지한 제어 스택은 실제 `CREATE_COMPLETE`다.
배포 매개변수와 ZIP SHA-256이 검토 계획과 일치한다. 앱과 제어 함수 모두 새 코드가
반영됐으며 앱/기존 NAT/새 제어 예약은 계속 DISABLED다.

실제 제어 함수의 NAT 기동, SSM 전달 규칙·독립 타이머 확인, 현재 LaunchTime에 묶인
READY 증명, 같은 시작 요청의 중복 차단을 통과했다. 새 이미지의 사설 Fargate doctor는
15항목/exit 0이며, 과거 ENTRY 예약 요청은 실제 컨테이너에서 EXPIRED_SCHEDULE/exit 2로
차단됐다. 시험용 사설 작업을 남긴 종료 검사에서 제한 대기 후 작업 강제 정리 완료와
NAT 정지를 확인했다. 최종 NAT stopped다. 증권사 주문은 제출하지 않았다.

제어 CloudWatch에는 정상 진단 종료 IGNORED 1회와 실패 감시 ALERTED 2회가 기록됐다.
사람이 확인하는 이번 텔레그램 수신은 답변 대기다. 실제 실패 이벤트의 중복 알림 차단,
정상 거래 시간의 앱 전체 실행 잠금·지갑·체결 흐름까지 완료한 것으로 표시하지 않는다.
doctor는 새 runtime_safety 실행 경로 자체를 호출하지 않는다.

다음은 네트워크 IAM 관리자 반영과 검토된 UserData 단독 갱신이다.
`paper-network-iam-bootstrap.yaml`의 추가분은 서울·기존 NAT 두 태그로 제한한
StartInstances와, 해당 IAM 스택 하나의 DescribeStacks/GetTemplate 읽기다. 기존 작업
계정으로는 이 IAM 스택 조회가 실제 거부돼 반영 후 원격/소스 일치를 확인할 수 있도록
읽기만 준비했다. IAM 수정 권한이나 전역 삭제 권한은 추가하지 않았다. 로컬 전체
249개/skip 0, 다섯 템플릿 lint/안전 검사, AWS ValidateTemplate을 통과했다.
중간 Docker 엔진 500 오류는 정상 재시작 후 재검사로 해소했다.

실제 120분 타이머 만료 정지, UserData 반영 후 재기동, 미래 5거래일 검증은 남아 있다.
이미지의 기존 미해결 취약점 69개(High 14) 조건부 판정도 유지한다. 자동 예약을 켜거나
실거래 승인으로 해석하지 않는다. 원문 증거는 Git 제외 runtime에 보존한다.

## 2026-10-18 앱 배포 권한과 예약 실행 보완

### 자동운용 보완 후속 — 로컬 249개 통과, 새 코드 미배포

후속 확인: 관리자 최신 task boundary 반영과 새 앱 UPDATE_COMPLETE를 확인했다.
TaskDefinition/TaskRole 직접 변경에 따른 예약 역할/11개 예약 Target 참조 갱신까지
검토해 반영했으며 예약 State는 계속 OFF다. 검증한 새 ECR digest와 실제 앱이 일치한다.
아래 미배포 설명은 이 확인 전의 경과이며 **제어 함수 스택은 아직 미생성**이다.

제어 함수 예약 동시 실행 2개를 적용하기 전에 계정 한도를 확인한다. AWS는 최소100의
미예약 동시 실행을 남기도록 요구한다. 작업 계정 GetAccountSettings 권한은 없으므로
관리자 CloudShell에서 limit/unreserved 숫자만 조회하도록 안내했다. 한도 확인 전
생성을 진행하지 않으며 제한을 임의 제거하지 않는다.
공식 기준: https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html

크레딧 충전 후 정상 명령 실행이 복구됐다. 보류한 인프라/구문/공백 검사와 서울 공개
단가 조회를 완료했다. 새 이미지도 빌드·소스39개 일치·전체249개 검사·오프라인 CVE
동일 판정·ECR digest 재다운로드 검증을 마쳤다. 새 앱/제어 함수는 아직 배포 전이다.
관리자 앱 IAM 업데이트와 `runtime/paper-control-console-20261018.yaml`의 제어 스택
등록이 다음 수동 단계다. 식별자를 채운 파일은 Git에 넣지 않는다.

제어 Lambda 일반 서울 단가로 128MiB/100회/매번 최대600초의 예시는 요청·실행 합계
약 $0.12502다(로그·저장 요청 별도, 프리티어/세금/크레딧 미적용). 총액 보장이나 호출량
상한이 아니며 기존 전체 월 $7~10 예상 범위를 유지하도록 검토한다.
공식 단가: https://aws.amazon.com/lambda/pricing/

현재 기동과 맞는 준비 증명/egress 확인, 예약 전체의 조건부 실행 잠금, 승인된 달력
범위 및 다음 거래일 검사를 로컬 코드에 추가했다. 특별 세션은 변경 시간을 추측하지
않고 차단한다. 별도의 `paper_control.py`/`paper-control.yaml`은 기존 NAT의 기동별
SSM 준비 확인과 작업 종료 연동·제한 초과 정리·실패 알림을 짧은 Lambda로 구성한다.
새 예약 6개도 DISABLED만 허용하며 기존 2시간 독립 정지 타이머를 유지한다.
`package_paper_control.py`는 비밀정보 없이 검토한 Python 세 파일만 결정적 ZIP으로 묶는다.

전체 249개 테스트/skip 0 및 다섯 템플릿 검사 한 차례를 통과했다. 새 코드의 실제
이미지/제어 함수·IAM·앱 배포와 실제 오류/중복 전달 검증은 아직 하지 않았다. 마지막
인프라 최종 재검사·구문/공백 검사 및 서울 공개 단가 조회는 작업 공간 크레딧 부족으로
자동 승인 검토가 실패해 실행되지 않았다. 검토 우회를 하지 않고 이 상태를 보존했다.
크레딧 문제가 해결되면 해당 검사와 비용 검토부터 재개한다. 기존 월 $7~10 예상 범위
밖으로 임의 확대하지 않으며 새 제어 함수도 아직 생성하지 않았다.

아래 실제 AWS 진단 15개 성공은 **직전 배포 버전**의 결과다. 새 runtime_safety와
제어 함수의 실제 AWS 검증 결과로 사용하지 않는다. 마지막 원격 조회에서는 NAT
stopped, 실행/대기 작업 0개, 기존 예약 OFF였으며 이번 작업에서 원격을 변경하지 않았다.

### 최신 확인 결과 — 실제 AWS 단발 통합 통과

앱 `UPDATE_COMPLETE`, 실제 사설 Fargate doctor **15개 항목 모두 true/exit 0**를
확인했다. 기대 고정 IP 일치, 키움 demo/OpenDART 읽기, 임시 폴더 쓰기/읽기/정리,
S3 validation 객체 저장/읽기, DynamoDB 두 항목 원자적 기록·중복 거부·원본 유지·
조건부 정리, 텔레그램 테스트 전송을 통과했다. 사용자가 실제 텔레그램 수신도 확인했다.
이는 연결/기본 저장 계약 검사이며 전략별 지갑·실제 모의 체결·운영 중복 전달 검증의
완료가 아니다. 증권사 주문은 제출하지 않았다.

관리자가 `AWSServiceRoleForECS` 부재를 확인하고 공식 서비스 연결 역할 생성 명령을
완료한 뒤 실제 Fargate 작업 기동에 성공했다. 검사 종료 후 NAT stopped, 실행/대기
작업 각각 0개, DDB 항목 0개, EIP 유지와 앱/NAT 예약 비활성 매개변수를 재확인했다.
S3에는 config 두 객체와 비밀값 없는 validation 객체 하나를 보존한다.

로컬 검증은 최종 216개 통과/skip 0다. 자동 모의운용 전에는 아래 준비/종료 연동·
실제 타이머 만료·UserData 차이·달력·중복/지연/외부 실패 알림 검증을 계속해야 한다.
아래 배포 실패·미검증 설명은 이 결과에 이르기까지의 경과로 읽는다.

사용자가 AWS 고정 IP를 키움 **모의투자** 허용 IP에 등록 완료했다고 보고했다.
이는 사용자 확인이며 실제 Fargate에서 키움 인증 성공을 확인한 결과는 아니다.
지정 작업 계정으로 네트워크 `CREATE_COMPLETE`, 예약 `DISABLED`, NAT `stopped`,
고정 IP 유지를 재조회했다. 콘솔의 스택 목록 조회는 작업 계정에 허용되지 않으므로
알려진 스택에 대한 `describe-stacks` 출력 조회를 사용한다. 목록 표시 오류를 스택
삭제나 배포 실패로 해석하지 않는다.

### 관리자 앱 IAM 등록

사전 확인: IAM 역할 `AWSServiceRoleForECS`는 앱 실행 역할과 별개의 AWS 표준
서비스 연결 역할이다. 없으면 관리자 CloudShell에서 아래 명령으로 생성한다.
작업 사용자의 IAM 권한을 넓히거나 이 역할을 앱 정리 대상으로 삭제하지 않는다.

```bash
aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com --query Role.RoleName --output text
```

1. 관리자 권한 콘솔의 서울 CloudFormation에서 새 스택 생성을 선택한다.
2. `paper-app-iam-bootstrap.yaml`을 파일 업로드한다. 파일은 JSON 형식으로 작성한
   유효한 CloudFormation 템플릿이며 `.yaml` 확장자로도 AWS 검증을 통과한다.
3. 스택 이름 `stock-automation-paper-app-iam`, 사용자 이름 `stock-paper-operator`를
   사용한다. 기존 네트워크 IAM 스택을 이 파일로 교체하지 않는다.
4. IAM 경계 관리형 정책 3개, 앱 CloudFormation 배포 역할 1개, 작업 사용자 관리형
   정책 1개, 총 5개 IAM 자원을 검토한다. 이름 지정 IAM 생성 확인 후 생성한다.
   이 스택 자체는 ECS 작업·데이터베이스·서버·IP를 생성하지 않는다.
5. `CREATE_COMPLETE` 후 작업 계정에서 지정 앱 스택 배포 권한이 적용됐는지 확인한다.
   관리자는 직접 배포 역할을 작업 계정에 광범위하게 붙이지 않는다.

앱은 고정된 모의 버킷·테이블·로그·클러스터 이름을 사용한다. `/stock-paper/` 경로의
실행·작업·예약 역할마다 별도의 permissions boundary를 요구한다. 실행 역할은 기존
demo/OpenDART Secret과 자체 ECR/로그만, 작업 역할은 모의 저장소와 텔레그램 Secret·
모의 SNS만, 예약 역할은 모의 작업 정의와 지정 실행/작업 역할 전달만 허용한다.
작업 사용자에는 Secret 값 조회·IAM 편집·앱 저장소 삭제를 부여하지 않는다.
현재 경계는 텔레그램용이며 Kakao 토큰 갱신 권한을 제공하지 않는다.
로컬 권한 계약 검사는 AWS IAM 시뮬레이션이나 실제 배포 성공의 대체가 아니다.

### 예약 시각·실행 제한

모든 예약 입력은 AWS 공식 `<aws.scheduler.scheduled-time>`을 `SCHEDULED_AT`으로
전달한다. 재시도 때의 현재 시각으로 원래 예약 날짜를 바꾸지 않는다.
출처: https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-context-attributes.html

| 단계 | 마지막 허용 시작 KST | 최대 실행 시간 |
|---|---|---|
| SCAN_1450 | 14:54:00 | 300초 |
| SHORTLIST_1510 | 15:13:00 | 180초 |
| ENTRY_1520 | 15:20:59 | 60초 |
| EXIT_0905 | 09:07:00 | 120초 |
| EXIT_0910 | 09:12:00 | 120초 |
| MEDIUM_ENTRY_0915 | 09:17:00 | 180초 |
| MEDIUM_REVIEW_1535 | 15:37:00 | 180초 |
| MEDIUM_SIGNAL_1540 | 15:42:00 | 180초 |
| EQUITY_SNAPSHOT_1550 | 15:53:00 | 180초 |
| 토요일 TUNE_WEEKLY | 08:05:00 | 1,200초 |

`aws-run`은 시간 검증 후 별도 작업 프로세스를 감독한다. 작업 프로세스도 시작 시각을
재검사해 느린 기동·이전 날짜 전달·만료·잘못된 단계·실거래 모드를 부작용 전에 차단한다.
제한 시간 초과 시 자식 프로세스를 종료/회수하고 `RUN_TIMED_OUT`을 기록한다.
직접 모듈 실행도 기본적으로 같은 감독 경로를 사용한다. 수동 단타는 예약 시각을
받지 않는 명시적 단발 실행만 허용하며 기존 장중 허용 창 안에서 최대 300초다.

실행 제한 초과는 `NO_TRADE`나 원장 미기록을 뜻하지 않는다. 종료와 동시에 진행 중인
DynamoDB 트랜잭션이 이미 확정됐을 수 있으므로 기존 원장과 outbox를 먼저 대사한다.
감독자는 자동 재실행하지 않는다. 원래 원장의 중복 조건·원자적 트랜잭션은 유지한다.
실패 구조화 로그는 추가했지만 ECS 실패를 텔레그램으로 보내는 외부 알림 경로와
실제 AWS 중복/지연 전달 검증은 아직 완료하지 않았다.

### 2026-10-18 이미지·통합 진단 준비와 첫 앱 배포 복구

- 관리자 앱 IAM 최신본의 `UPDATE_COMPLETE`와 원격/로컬 템플릿 일치를 확인했다.
  첫 앱 생성은 이름 기반 `iam:GetRole` 권한 누락으로 실패했고, 롤백의
  `iam:DeleteRolePolicy`도 거부됐다. 기존 세 역할 이름에 한정한 조회·실패 정리
  권한을 보완했다. 역할 생성/정책 쓰기는 기존 경로·permissions boundary를 유지한다.
  수정 후 실패 앱 스택만 `DELETE_COMPLETE`로 정리했다. 재생성 성공은 아직 미검증이다.
- 실패 배포가 만든 S3/DynamoDB는 Retain으로 남았다. CloudFormation의 물리 자원
  매핑과 Project 태그를 대조하고, S3 객체 0개와 DynamoDB 강한 일관성 조회 0개를
  확인했다. AWS 스택 소유권 태그는 없으므로 태그 일치로 소유권을 확인했다고
  주장하지 않는다. 작업 계정에 데이터 삭제 권한을 추가하지 않고 관리자가 해당
  빈 자원만 정리한다. 첫 실패·자원 목록·검증 원문은 Git 제외 runtime에 보존한다.
- 최종 `stock-automation:paper-aws-20261018` 이미지는 linux/amd64로 새로 빌드했다.
  소스/정적 파일 38개 해시와 실제 격리 검사를 통과했고 ECR 업로드 후 digest,
  rootfs, 실행 사용자와 동일 소스를 확인했다. 사설 레지스트리 URI는 runtime에만 둔다.
- Windows 자격 증명 저장 오류는 공식 ECR credential helper로 해결했다. 공개
  릴리스 체크섬을 검증하고 임시 Docker 설정과 `AWS_ECR_DISABLE_CACHE=true`를
  사용했다. 전역 Docker 설정을 바꾸거나 인증 토큰을 평문으로 저장하지 않았다.
- Grype 공개 DB(2026-10-18 빌드)를 별도 갱신한 뒤 외부 연결을 막은 로컬 이미지
  아카이브 검사에서 203개 패키지/CVE 조합, 고유 94개를 확인했다. 버전·심각도·수정
  상태를 포함한 결과는 이전 검토와 같았다. 이전 분류의 Debian backport 해결 25개와
  미해결 69개(High 14개) 조건부 판정을 적용하며 취약점 0개·패치 완료로 표시하지 않는다.
  Docker Scout나 외부 서비스에 이미지/SBOM 메타데이터를 보내지 않았다.
- 키움 모의 TR별 최소 1초 간격을 추가했다. 동일 프로세스에서 실패·재시도·연속조회도
  포함하지만 여러 동시 작업 사이의 분산 제한은 아니다. 비용 기준은 사용자가 선택한
  매수/매도 각각 1.5bps, 매도세 20bps이며 개인 우대 수수료 확인값은 아니다.
- `doctor --online --aws --write-probes --test-notification`을 준비했다. 기대 EIP
  확인 실패 시 API/저장/알림보다 먼저 중단하고, 저장 검사는 별도 probe 키만 사용한다.
  실제 Fargate 진단·텔레그램 발송은 아직 하지 않았다. 기본 doctor는 읽기 전용이다.
- 2026년 달력 파일은 특별 세션/다음 거래일 검증 미완료로 자동 운용 적격이 아니다.
  앱 템플릿은 Core/NXT 상태의 허용값 자체를 DISABLED로 제한한다.
- 최종 전체 검사 214개 통과/skip 0, 인프라 네 템플릿 검사 및 AWS 템플릿 검증 통과.
  중간 Docker 엔진 HTTP 500 실패는 정상 재시작 후 해소했다. 데이터 초기화는 하지 않았다.

이후 실제 재생성에서 역할 생성은 성공했으나 Scheduler Input의 PascalCase JSON을
ECS TaskOverride로 해석할 수 없어 실패했다. 11개 예약을 공식 lowerCamelCase
(`containerOverrides/name/environment/name/value`)로 수정하고 botocore ECS 모델에
따른 입력 검증 및 잘못된 대소문자 거부 검사를 추가했다. 수정 뒤 전체 **216개 통과/
skip 0**와 네 템플릿 검사·AWS ValidateTemplate을 확인했다. 앞선 214개 실행 결과와
이후 수정 후 검증을 구분한다.

롤백의 `DeregisterTaskDefinition`은 AWS가 자원 ARN 제한을 지원하지 않아 기존
제한 권한으로 거부됐다. 전역 등록 해제 권한을 추가하지 않고 해당 미실행 작업
정의를 RetainResources로 보존해 실패 스택을 정리했다. 작업 정의는 실행 중 서버가
아니며 기록만 남는다. 이후 템플릿도 TaskDefinition을 Retain/UpdateReplacePolicy
Retain으로 설정한다. `DescribeTaskDefinition`만 AWS 지원 범위에 맞춰 서울 리전
메타데이터 읽기(`Resource: *`)로 보완했으며 관리자 반영 확인이 필요하다.
공식 명세: https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html

두 번째 실패의 빈 저장소는 추가 삭제 대신 기존 승인 범위의 LogGroup을 먼저 만든
앱 스택으로 가져온다. 새 스택 IMPORT에서 RoleArn/Tags 추가가 허용되지 않아 처음
변경 세트가 검증 실패했으며, 같은 역할/태그로 로그 그룹을 먼저 만든 뒤 기존 S3와
DynamoDB 두 개의 Import만 있는 변경 세트를 검토·실행했다. 가져오기 완료와 나머지
앱 자원 추가 배포의 결과는 별도로 확인해야 한다. 초기 실패 상태와 가져오기 기록을
덮어쓰지 않으며 데이터 삭제 권한은 계속 부여하지 않는다.

저장소 가져오기는 `IMPORT_COMPLETE`, 같은 두 물리 자원 유지까지 확인했다. 이후
기존 세 자원의 변경 없이 17개 자원 Add를 검토·실행해 앱 `UPDATE_COMPLETE`를
확인했다. 예약 비활성과 공인 IP 할당 금지 매개변수를 재확인했고, 실제 ECS 작업
정의는 검증한 ECR digest·demo/LIVE_ORDER_ENABLED=0·비루트·읽기 전용 설정이었다.

첫 단발 진단의 `ListTasks`는 기존 클러스터 ARN 정책으로 거부됐다. 추가 권한 대신
이미 허용된 `DescribeClusters`의 running/pending task count가 모두 0임을 확인하는
방식으로 중복 실행 검사를 했다. 기존 ListTasks 권한이 실제 사용 가능하다고
주장하지 않는다. S3 달력/비용 업로드와 읽기 일치 검사는 완료했다.

이후 NAT를 잠시 켜 매 기동 실제 IP forwarding·FORWARD 기본 DROP·기존 연결/사설
HTTPS 허용·MASQUERADE·iptables 활성·독립 정지 타이머 활성/설정 검사를 통과했다.
이는 수동 기동 검사이며 예약 런타임 준비 확인의 자동화나 실제 120분 만료 정지 검증은
아니다. Fargate RunTask는 두 번 모두 `Unable to assume the service linked role`
오류로 **작업을 시작하지 못했다**. 키움/OpenDART/원장/텔레그램 성공은 미검증이다.
두 창 모두 finally 정리로 NAT `stopped`를 확인했다.

관리자 IAM에서 `AWSServiceRoleForECS`가 있는지 확인하고 필요하면 AWS 공식
`ecs.amazonaws.com` 서비스 연결 역할을 만든다. 앱 실행/작업 역할로 대체하거나
작업 사용자에게 광범위한 IAM 편집 권한을 추가하지 않는다. 계정 공용 서비스 연결
역할이므로 앱 실패 정리 과정에서 삭제하지 않는다.
공식 절차: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using-service-linked-roles-for-clusters.html

### 아직 예약을 켜지 않는 이유

- 매 기동 NAT 실제 준비 확인과 사설 Fargate HTTPS/EIP 경로 검증이 남아 있다.
- 실행 중 ECS 작업을 확인하고 정지/실패 정리하는 네트워크 종료 연동이 남아 있다.
- 독립 120분 타이머의 실제 만료 정지 및 원격 UserData 차이 검증이 남아 있다.
- 앱 재배포, 특별 세션/다음 거래일 검증, API·저장·알림 실제 통합이 남아 있다.
- 이미지 재검사·ECR 업로드는 위 결과까지 완료했지만 미해결 취약점과 실제 AWS
  격리 검증은 계속 관리해야 한다. 실제 중복 전달/실패 알림 검증도 남아 있다.

이 시간 제한은 NAT 실행 창을 늘리지 않으며 예약 활성화의 충분조건이 아니다.

## 1. 관리자가 네트워크 배포 권한을 한 번 등록

작업 계정에는 기존 Secret 등록·ECR 업로드·네트워크 조회 권한만 있다. 아래 IAM
전용 스택은 관리자 권한이 있는 콘솔에서 등록한다. 작업 계정에 관리자 정책을 붙이거나
CLI에서 root 프로필로 전환하지 않는다.

1. 서울 리전(`ap-northeast-2`)의 **CloudFormation**을 연다.
2. **스택 생성 → 새 리소스 사용(표준)**을 선택한다.
3. **기존 템플릿 선택 → 템플릿 파일 업로드**를 선택한다.
4. 같은 폴더의 `paper-network-iam-bootstrap.yaml`을 업로드한다.
5. 스택 이름은 `stock-automation-paper-network-iam`, 사용자 이름은
   `stock-paper-operator` 그대로 입력한다.
6. 나머지 설정은 기본값을 유지한다. 검토 화면에서 이름이 지정된 IAM 리소스 생성
   안내를 확인하고 생성한다. `CREATE_COMPLETE`를 확인한다.

이 스택은 NAT 호스트의 SSM 역할/프로필, 시작·정지 역할, 네트워크 전용 CloudFormation
서비스 역할, 작업 계정의 관리형 정책을 만든다. EC2·EIP·앱은 아직 만들지 않는다.
배포 역할은 서울의 프로젝트 태그 자원을 관리하고 기존 VPC/공개 서브넷을 참조한다.
`t3.micro`, IMDSv2, 암호화 gp3 8GiB와 지정된 역할 전달만 허용한다. Secret 값 조회와
IAM 편집 권한은 없다. **앱 스택 배포 권한은 별도로 준비·확인할 대상**이다.

이미 이 IAM 스택을 만든 뒤 파일이 갱신됐다면 **기존 IAM 스택 선택 → 업데이트 →
현재 템플릿 교체 → 템플릿 파일 업로드**로 최신 파일을 적용한다. 새 IAM 스택을
같은 역할 이름으로 중복 생성하지 않는다. 2026-10-14 최초 네트워크 실행은 생성 전
가용영역 매개변수 검증의 `ec2:DescribeAvailabilityZones` 누락으로 롤백됐다.
수정본은 이 서울 조회 권한과 지정 네트워크 스택의 정리 권한을 추가한다.
적용 후 실제 생성 자원이 없는 `ROLLBACK_COMPLETE` 네트워크 스택만 확인해
정리한 뒤 새 변경 세트로 재시도한다. IAM 스택과 기존 VPC·Secret·이미지는 보존한다.

## 2. PC-C가 실제 상태를 조회해 매개변수 준비

프로젝트 최상위에서 실행한다. AWS 조회만 하며 자원을 생성하지 않는다.

```powershell
.\.venv\Scripts\python.exe stock-automation/tools/prepare_fixed_egress.py
```

VPC DNS 두 설정, 공개 서브넷의 실제 IGW 경로, 같은 AZ의 새 사설망, Amazon 소유
AL2023 x86_64 AMI와 최소 루트 디스크를 확인한다. 기존 `10.77.0.0/20`과
`10.77.16.0/20`을 피한 첫 /24는 `10.77.32.0/24`다. 실제 조회 결과를 우선한다.
AMI에 8GiB보다 큰 디스크가 필요하면 임의로 늘리지 않고 예산 영향을 다시 검토한다.
결과는 Git 제외 `runtime/paper-network-parameters.json`에 저장한다. 기존 결과는
덮어쓰지 않으므로 검토·별도 보존 후 재생성한다. 식별자·키·원본 로그를 Git에 옮기지 않는다.

## 3. 네트워크 스택 배포와 최초 부팅 확인

PC-C가 매개변수와 `paper-fixed-egress.yaml`, `stock-paper-network-deployer` 역할로
이름이 정확히 `stock-automation-paper-network`인 스택을 만든다. `StartScheduleState=DISABLED`다.
`create-stack` 또는 명시적 `paper-network-*` 변경 세트 이름을 사용한다. 일반
`aws cloudformation deploy`의 자동 변경 세트 이름은 이 제한된 정책 범위에 없다.

새 사설 서브넷 1개, 전용 경로/보안 그룹/인터페이스, NAT EC2 1대, EIP 1개다.
인터페이스에 EIP를 먼저 붙인 뒤 호스트를 부팅한다. NAT에는 앱과 키움 키를 넣지 않는다.
사설망 TCP 443만 전달하고 SSH는 열지 않는다. 앱의 공인 IP 할당은 차단한다.
EC2는 예약 비활성과 별개로 최초 생성 시 부팅하므로 검증 후 즉시 정지한다.
OS 독립 정지 타이머는 패키지 설치 전에 등록하고 매 부팅 2시간 뒤 정지한다.
OS/타이머 장애까지 지출을 강제로 제한하지는 않으므로 실제 EC2 상태를 확인한다.

`CREATE_COMPLETE`만으로 준비 완료를 선언하지 않는다. SSM으로 cloud-init 성공,
IP forwarding, iptables 규칙과 재부팅 후 유지, 정지 타이머 활성 상태를 확인한다.
실제 사설 Fargate 작업의 HTTPS 연결과 관찰된 공인 IP가 EIP와 일치하는지도 확인한다.
실패하면 앱 예약을 켜지 않는다.

### 2026-10-14 PC-C 실제 검증 상태

관리자 IAM 수정 적용 후 네트워크 스택은 `CREATE_COMPLETE`가 됐다. 실제 EIP 연결,
사설망 경로/공인 IP 차단, HTTPS 인바운드 제한, IMDSv2, 8GiB 디스크와 SSM 연결을
확인했다. 첫 설치는 60초 dnf 제한으로 끝나지 않아 cloud-init이 실패했고, SSM으로
600초/최대 2회 제한의 현재 bootstrap을 다시 적용해 복구했다. IP forwarding,
iptables 서비스/저장 규칙, 독립 정지 타이머 검사를 통과했다. 실제 정지→기동 뒤
cloud-init 성공, 같은 EIP, 전달 규칙/타이머 유지도 확인했고 다시 정지했다.

현재 로컬 템플릿은 설치 제한을 600초로 개선했지만 **배포된 CloudFormation의
UserData 속성은 최초 60초 버전**이다. 실행 중 호스트는 SSM 복구한 상태이고
재기동 검증을 통과했다. 향후 UserData 템플릿 업데이트는 재시작 및 배포 역할의
해당 EC2 권한을 검토하고 수행한다. 예약만 갱신할 때는 원격 기존 템플릿을 유지하는
방식으로 bootstrap 변경을 섞지 않는다. 이 차이를 실제 배포 완료로 숨기지 않는다.

모든 예약은 아직 DISABLED다. **실제 사설 Fargate egress·키움 허용 IP 등록·앱 스택·
온라인 API/저장/알림 통합검증은 미완료**이며 서버 생성과 모의운용 시작을 구분한다.

## 4. 키움 등록과 앱 온라인 통합검증

새 EIP를 **키움 모의투자 키**의 허용 IP에 등록한다. 기존 PC IP는 등록 한도 내에서 유지한다.
최신 `/tmp` 권한 이미지의 검증된 ECR digest, 사설 서브넷과 기존 작업 보안 그룹을
앱 스택에 전달한다. `AssignPublicIp=DISABLED`, 핵심/NXT 예약 모두 `DISABLED`다.

앱 배포 권한, 확인된 수수료·세금, KRX 전체 휴장일 파일, 실제 Fargate `/tmp` 쓰기,
키움 demo·OpenDART 조회, S3/DynamoDB 원장·멱등성, 텔레그램 전달은 각각 확인할 대상이다.
키·계좌·개인 식별자·응답 원문은 로그/Git에 저장하지 않는다. 앱의 AI 모의체결 기록과
증권사에 제출하는 모의 주문을 구분한다. 현재 앱은 AI 모의체결을 기록한다.

## 5. 검증 완료 후 모의 예약 시작

핵심 앱 예약과 NAT 시작·정지 예약을 함께 활성화한다. NXT/상시 단타는 켜지 않는다.

| NAT 실행 창(KST) | 포함하는 앱 작업 |
|---|---|
| 평일 08:55~09:25 | 09:05 점검, 09:10 청산, 09:15 중기 진입 |
| 평일 14:40~16:10 | 14:50 스캔, 15:10 재검증, 15:20 진입, 15:35/40/50 후속 작업 |
| 토요일 07:50~08:40 | 08:00 주간 튜닝 |

시작은 5분까지만 재시도한다. 실제 부팅·재시도·작업 완료 시간이 창 안에 드는지
검증하기 전에는 다음 거래일 자동 실행을 확정하지 않는다. 정지 전에 실행 중 작업이
없는지 확인한다. 창을 넘는 작업/늦은 재시도는 별도 보완 대상이다.
22거래일·토요일 4회면 NAT 약 47.3시간/월이다. EIP는 정지 중에도 요금이 발생한다.
디스크·기존 Secret/ECR·앱 단기 실행·로그 포함 전체 $7~10은 예상 범위이며 지출 상한은 아니다.

## 로컬 검증

앱 의존성과 분리된 검증 도구 경로를 사용한다.

```powershell
.\.venv\Scripts\python.exe -m pip install --target runtime/infra-validation -r stock-automation/infra/requirements-validation.txt
$env:PYTHONPATH = "runtime/infra-validation"
.\.venv\Scripts\python.exe stock-automation/tools/validate_paper_infrastructure.py
$env:PYTHONPATH = "stock-automation/src"
.\.venv\Scripts\python.exe -m unittest discover -s stock-automation/tests
```

로컬 스키마/IAM/안전 구조 검사이며 AWS 생성이나 SBOM 전송은 없다. 실제 배포·원격
권한·온라인 API 성공은 별도 확인이다.

공식 근거: [NAT 구성](https://docs.aws.amazon.com/vpc/latest/userguide/work-with-nat-instances.html),
[Scheduler API 대상](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html),
[CloudFormation 서비스 역할](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html),
[DynamoDB 거래 IAM](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html),
[공인 IPv4 비용](https://aws.amazon.com/vpc/pricing/).
