"""User-run creation of three named paper secrets; never prints secret values.

Install tools/requirements.txt. --create explicitly authorizes this paid action.
Existing secrets are never overwritten. Partial successes remain stored in AWS.
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import re
import sys
import uuid

PROFILE = "stock-paper-operator"
REGION = "ap-northeast-2"
NAMES = (
    "stock-automation-paper/kiwoom-demo",
    "stock-automation-paper/dart",
    "stock-automation-paper/telegram",
)


class UploadError(Exception):
    """All messages are fixed text, without SDK exception details."""


def is_not_found(exc) -> bool:
    response = getattr(exc, "response", None)
    return isinstance(response, dict) and response.get("Error", {}).get("Code") == "ResourceNotFoundException"


def preflight(sts, secrets) -> None:
    identity = sts.get_caller_identity()
    if not str(identity.get("Arn", "")).endswith(":user/stock-paper-operator"):
        raise UploadError("지정한 IAM 사용자가 아닙니다. 저장을 중단합니다.")
    for name in NAMES:
        try:
            secrets.describe_secret(SecretId=name)
        except Exception as exc:
            if not is_not_found(exc):
                raise UploadError("AWS 권한 또는 연결 확인에 실패했습니다. 아무 키도 생성하지 않았습니다.") from None
        else:
            raise UploadError("같은 이름의 Secret이 이미 있습니다. 덮어쓰지 않고 중단합니다.")


def build_payloads(app_key: str, app_secret: str, dart_key: str, telegram_raw: str):
    app_key, app_secret, dart_key = app_key.strip(), app_secret.strip(), dart_key.strip()
    if any(not value or any(char.isspace() for char in value) for value in (app_key, app_secret)):
        raise UploadError("모의투자 App Key 또는 Secret 입력 형식을 확인하세요.")
    if not re.fullmatch(r"[A-Za-z0-9]{40}", dart_key):
        raise UploadError("OpenDART 인증키는 40자리 키만 입력하세요.")
    try:
        telegram = json.loads(telegram_raw)
        token, chat_id = telegram["bot_token"], telegram["chat_id"]
        if not isinstance(token, str) or not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError
        if not isinstance(chat_id, str) or not re.fullmatch(r"[1-9][0-9]*", chat_id):
            raise ValueError
    except Exception:
        raise UploadError("로컬 텔레그램 등록을 확인할 수 없습니다. 등록 도구를 다시 실행하세요.") from None
    return (
        {"app_key_mock": app_key, "app_secret_mock": app_secret},
        {"dart_api_key": dart_key},
        {"bot_token": token, "chat_id": chat_id},
    )


def create_all(secrets, payloads, *, progress=print) -> None:
    if len(payloads) != len(NAMES):
        raise UploadError("저장할 키 구성에 오류가 있습니다.")
    for name, payload in zip(NAMES, payloads):
        try:
            secrets.create_secret(
                Name=name,
                Description="Scheduled stock automation: paper setup only",
                ClientRequestToken=str(uuid.uuid4()),
                SecretString=json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            raise UploadError("AWS 저장이 중단됐습니다. 앞서 완료 표시가 나온 항목은 유지됩니다. 오류 문구만 알려주세요.") from None
        progress("저장 완료: " + name.rsplit("/", 1)[-1])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="서울 리전에 모의용 키 3개를 안전하게 저장합니다.")
    parser.add_argument("--create", action="store_true", help="비용 안내 승인 후 실제 Secret 3개 생성")
    args = parser.parse_args(argv)
    if not args.create:
        print("준비된 작업: 서울 리전 모의용 Secret 3개 생성. 비용 승인 후 --create로 실행하세요.")
        return 0
    if sys.platform != "win32" or not sys.stdin.isatty():
        print("본인 Windows PowerShell 또는 CMD 창에서 직접 실행하세요.")
        return 1
    try:
        # This CLI configures native TLS before importing the AWS SDK.
        import truststore
        truststore.inject_into_ssl()
        import boto3
        from keyring.backends.Windows import WinVaultKeyring

        for name in ("boto3", "botocore", "urllib3"):
            logging.getLogger(name).disabled = True
        session = boto3.Session(profile_name=PROFILE, region_name=REGION)
        secrets = session.client("secretsmanager")
        preflight(session.client("sts"), secrets)
        telegram_raw = WinVaultKeyring().get_password("stock-automation-setup", "telegram")
        if telegram_raw is None:
            raise UploadError("로컬 텔레그램 등록이 없습니다. 먼저 등록 도구를 실행하세요.")
        print("키움 모의투자 키만 입력하세요. 입력한 값은 표시되지 않습니다.")
        app_key = getpass.getpass("모의투자 App Key: ")
        app_secret = getpass.getpass("모의투자 Secret: ")
        dart_key = getpass.getpass("OpenDART 인증키: ")
        payloads = build_payloads(app_key, app_secret, dart_key, telegram_raw)
        create_all(secrets, payloads)
        print("AWS 저장 완료: 모의용 Secret 3개. 예약 작업과 프로그램 배포는 다음 단계입니다.")
        return 0
    except UploadError as exc:
        print(str(exc))
    except (KeyboardInterrupt, EOFError):
        print("입력을 취소했습니다.")
    except Exception:
        print("AWS 로그인·연결 또는 로컬 환경 확인에 실패했습니다. 오류 문구만 알려주세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
