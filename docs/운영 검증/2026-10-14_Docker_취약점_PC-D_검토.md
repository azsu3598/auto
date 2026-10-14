# Docker 취약점 PC-D 검토

- 검토 시각: 2026-10-14 08:19 KST
- 대상 이미지 기록: `docs/운영 검증/2026-10-14_Docker_취약점_검증.csv`
- 기준 배포판: Debian trixie 기반 `python:3.13-slim-trixie`
- 적용 범위: 키움 모의투자용 예약 ECS Fargate 작업
- 실거래 상태: 비활성, 비상정지 기본 ON

## 결론

이미지 스캔에서 식별된 고유 미해결 항목은 69개이며 High 14개, Medium 25개,
Low 5개, Negligible 25개다. 2026-10-14 검토 시점에 High 14개 모두 Debian
trixie에서 설치 가능한 수정 버전이 없었다. 따라서 이 문서는 해당 항목을
`FIXED` 또는 오탐으로 닫지 않는다.

현재 프로그램은 High 취약점의 전제인 마운트·namespace 관리, ACL 변경, Perl 문서와
tar 처리, ncurses `infocmp`, C/C++ 대용량 할당 또는 zlib 비차단 `gzwrite`를 호출하지
않는다. ECS 작업도 비루트 사용자, 읽기 전용 루트 파일시스템, Linux capability 전체
제거, 쓰기 가능한 전용 `/tmp`로 강화했다. 이 조건에서는 **모의투자 통합검증만 조건부
진행**할 수 있다.

다만 노출 제한은 패치가 아니다. High 14개는 모두 미해결 상태로 남기며, 실거래 배포는
Debian 수정 패키지 또는 새 기반 이미지 확인, 재빌드·재스캔, PC-C 런타임 검증과 별도
위험 승인이 끝날 때까지 차단한다.

## High 14개 검토

| CVE | 소스 패키지 | 필요한 공격·호출 조건 | 현재 노출 판단 | 처리 |
|---|---|---|---|---|
| CVE-2025-69720 | ncurses | 공격자 입력을 `infocmp` CLI로 분석 | 프로그램에서 CLI 미호출 | 미해결·업데이트 감시 |
| CVE-2026-102010 | gcc-14/libstdc++ | C++ priority queue의 취약한 `erase_if` 호출 | Python 애플리케이션 경로에서 확인되지 않음 | 미해결·업데이트 감시 |
| CVE-2026-19499 | glibc | 취약한 형식으로 `strfmon`/`strfmon_l` 호출 | 코드에서 미호출 | 미해결·업데이트 감시 |
| CVE-2026-5435 | glibc | 폐기된 DNS 출력 함수와 TSIG 입력 처리 | 코드에서 미호출 | 미해결·업데이트 감시 |
| CVE-2026-54369 | acl | 권한 프로세스가 공격자 제어 경로의 ACL 처리 | 비루트·capability 없음·ACL 미호출 | 미해결·격리 완화 |
| CVE-2026-54370 | acl | 권한 프로세스의 ACL TOCTOU와 공격자 제어 경로 | 비루트·capability 없음·ACL 미호출 | 미해결·격리 완화 |
| CVE-2026-76642 | util-linux | 권한 있는 mount helper와 post-mount hook | 비루트·capability 없음·mount 미호출 | 미해결·격리 완화 |
| CVE-2026-78408 | util-linux | root `nsenter --join-cgroup` 실행 | 비루트·capability 없음·nsenter 미호출 | 미해결·격리 완화 |
| CVE-2026-78409 | util-linux | fstab 허용 `X-mount.subdir`와 로컬 공격자 | 비루트·capability 없음·mount 미호출 | 미해결·격리 완화 |
| CVE-2026-78410 | util-linux | SUID mount, 교체 가능한 경로와 fstab 항목 | 비루트·capability 없음·mount 미호출 | 미해결·격리 완화 |
| CVE-2026-82560 | perl | 공격자 제공 POD 문서를 `Pod::Text`로 변환 | Perl/POD 처리 미호출 | 미해결·업데이트 감시 |
| CVE-2026-85091 | zlib | 비차단 `gzwrite` 정지 후 `gzprintf`/`gzvprintf` | 직접 gz API 호출 없음; 공용 라이브러리이므로 계속 추적 | 미해결·우선 감시 |
| CVE-2026-9538 | perl | 조작된 tar 헤더를 Perl `Archive::Tar`로 처리 | Perl/tar 처리 미호출 | 미해결·업데이트 감시 |
| CVE-2026-95619 | gcc-14/libstdc++ | 매우 큰 aligned `operator new` 입력 | Python 애플리케이션 경로에서 확인되지 않음 | 미해결·업데이트 감시 |

Debian 공식 추적기는 ncurses, gcc-14, glibc, util-linux와 대부분 Perl 항목을
trixie의 `Minor issue` 또는 `no-dsa/postponed`로 분류한다. ACL 두 건은 trixie의
향후 point release 반영 대상으로 기록되어 있다. zlib 항목은 trixie를 취약 상태로
표시하면서 아직 고정 버전을 제시하지 않는다.

## 나머지 미해결 55개

| 심각도 | 고유 CVE | 주요 소스 패키지 | 방침 |
|---|---:|---|---|
| Medium | 25 | glibc 9, tar 3, python/sqlite3/systemd 각 2 등 | 호출 경로와 Debian 수정 버전을 재스캔마다 재검토 |
| Low | 5 | glibc 3, shadow 1, systemd 1 | 삭제 가능한 도구 여부를 이미지 단위로 재검토 |
| Negligible | 25 | glibc 7, coreutils/systemd 각 4 등 | 수용으로 닫지 않고 기반 이미지 업데이트로 추적 |

CSV의 203개 행은 하나의 CVE가 여러 바이너리 패키지에 연결되어 중복된다. 정책 판단은
고유 CVE 69개를 기준으로 하되, 패키지별 행은 SBOM 추적을 위해 유지한다. 이미 Debian
수정 버전이 확인된 고유 CVE 25개도 다음 이미지 스캔에서 재발 여부를 확인한다.

## 적용한 방어 계층

- 이미지와 ECS Task Definition 모두 `65534:65534` 비루트 사용자 지정
- ECS 루트 파일시스템 읽기 전용
- 모든 Linux capability 제거와 privileged 실행 금지
- Python 임시 작업에만 빈 `/tmp` 볼륨을 쓰기 가능하게 마운트
- `KIWOOM_MODE=demo`, `KIWOOM_TOKEN_STORE=memory`, `LIVE_ORDER_ENABLED=0` 명시
- 실계좌 Secret과 실거래 스케줄 미연결

## PC-C 재검증 조건

1. CloudFormation 변경을 검토하고 변경 세트를 생성하되 스케줄은 `DISABLED`로 유지한다.
2. Task Definition에 비루트 사용자, read-only root, capability drop과 `/tmp` 볼륨이
   그대로 반영되는지 확인한다.
3. 모의 `aws-run` smoke test에서 임시 디렉터리 사용, 키움 demo 읽기, S3·DynamoDB
   쓰기가 정상인지 확인한다.
4. 최신 base image로 `--pull --no-cache` 재빌드하고 동일 스캐너 DB로 다시 검사한다.
5. High 항목이 남으면 삭제·업데이트·실행 경로 차단 여부를 다시 기록한다. High를
   무시 목록에 넣어 0건으로 표시하지 않는다.

## 공식 근거

- [Debian CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720)
- [Debian CVE-2026-102010](https://security-tracker.debian.org/tracker/CVE-2026-102010)
- [Debian CVE-2026-19499](https://security-tracker.debian.org/tracker/CVE-2026-19499)
- [Debian CVE-2026-5435](https://security-tracker.debian.org/tracker/CVE-2026-5435)
- [Debian CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369)
- [Debian CVE-2026-54370](https://security-tracker.debian.org/tracker/CVE-2026-54370)
- [Debian CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642)
- [Debian CVE-2026-78408](https://security-tracker.debian.org/tracker/CVE-2026-78408)
- [Debian CVE-2026-78409](https://security-tracker.debian.org/tracker/CVE-2026-78409)
- [Debian CVE-2026-78410](https://security-tracker.debian.org/tracker/CVE-2026-78410)
- [Debian CVE-2026-82560](https://security-tracker.debian.org/tracker/CVE-2026-82560)
- [Debian CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091)
- [Debian CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538)
- [Debian CVE-2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619)
- [AWS Fargate Task Definition 제한과 지원 항목](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html)
- [AWS CloudFormation ECS ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-taskdefinition-containerdefinition.html)

## 제한 사항

PC-D에는 Docker가 설치되어 있지 않아 변경 후 이미지를 재빌드하거나 ECS Fargate에서
실행하지 못했다. 소스·템플릿 검증과 전체 Python 회귀 테스트는 PC-D에서 수행하고,
실제 컨테이너와 AWS smoke test는 PC-C가 담당한다.
