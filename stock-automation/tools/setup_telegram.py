"""User-run Telegram setup; credentials never appear in output or project files.

Uses only getMe/getUpdates, without an offset, webhook changes, or messages.
The saved JSON matches TelegramNotifier's future AWS Secrets Manager contract.
Install tools/requirements.txt in the local Python environment before running.
"""
from __future__ import annotations

import argparse
import getpass
import http.client
import json
import re
import socket
import ssl
import sys

SERVICE = "stock-automation-setup"
ACCOUNT = "telegram"


class SetupError(Exception):
    """Only fixed, secret-free messages may be used here."""


def secure_context():
    # Use native certificate validation, including the Windows trust store.
    # Never disable certificate or hostname verification, or alter global SSL.
    try:
        import truststore
    except ImportError:
        raise SetupError("필수 패키지가 없습니다. tools/requirements.txt를 설치하세요.") from None
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def telegram_get(token: str, method: str):
    if method not in {"getMe", "getUpdates"}:
        raise SetupError("허용되지 않은 조회입니다.")
    connection = http.client.HTTPSConnection("api.telegram.org", timeout=15, context=secure_context())
    try:
        query = "?limit=100&timeout=0" if method == "getUpdates" else ""
        connection.request("GET", f"/bot{token}/{method}{query}")
        response = connection.getresponse()
        if response.status != 200:
            if response.status == 401:
                raise SetupError("토큰 인증에 실패했습니다 (HTTP 401). BotFather 토큰을 확인하세요.")
            if response.status == 409:
                raise SetupError("대화 조회가 충돌했습니다 (HTTP 409). 오류 문구만 알려주세요.")
            raise SetupError("텔레그램 조회에 실패했습니다. 토큰과 인터넷 연결을 확인하세요.")
        # No redirects, raw API responses, exception strings, or URL logging.
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise SetupError("조회 응답이 너무 큽니다. 설정을 중단합니다.")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise SetupError("텔레그램 인증 또는 조회에 실패했습니다.")
        return payload.get("result")
    except SetupError:
        raise
    except ssl.SSLCertVerificationError:
        raise SetupError("서버 인증서 검증에 실패했습니다. 오류 문구만 알려주세요.") from None
    except socket.gaierror:
        raise SetupError("텔레그램 서버 주소를 찾지 못했습니다. 인터넷 연결을 확인하세요.") from None
    except TimeoutError:
        raise SetupError("텔레그램 연결 시간이 초과됐습니다. 잠시 후 다시 실행하세요.") from None
    except Exception:
        raise SetupError("텔레그램 연결 또는 응답 확인에 실패했습니다.") from None
    finally:
        connection.close()


def find_private_chat(updates, username: str) -> str:
    if not isinstance(updates, list):
        raise SetupError("대화 조회 응답을 확인할 수 없습니다.")
    candidates = set()
    for update in updates:
        if not isinstance(update, dict):
            continue
        message = update.get("message")
        if not isinstance(message, dict):
            continue
        chat, sender = message.get("chat"), message.get("from")
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            continue
        chat_id = chat.get("id")
        text = message.get("text", "")
        if not isinstance(text, str):
            continue
        words = text.strip().split()
        command = words[0].casefold() if words else ""
        if (
            chat.get("type") == "private"
            and type(chat_id) is int
            and chat_id > 0
            and sender.get("id") == chat_id
            and sender.get("is_bot") is False
            and command in {"/start", f"/start@{username.casefold()}"}
        ):
            candidates.add(str(chat_id))
    if not candidates:
        raise SetupError("개인 대화방에서 /start를 다시 보낸 뒤 이 도구를 재실행하세요.")
    if len(candidates) != 1:
        raise SetupError("여러 개인 대화방이 확인돼 자동 선택을 중단했습니다. 오류 문구만 알려주세요.")
    return candidates.pop()


def register(token: str, username: str, vault, *, api=telegram_get) -> None:
    token = token.strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise SetupError("토큰 형식이 올바르지 않습니다. BotFather의 토큰만 복사하세요.")
    me = api(token, "getMe")
    if (
        not isinstance(me, dict)
        or me.get("is_bot") is not True
        or str(me.get("username", "")).casefold() != username.casefold()
    ):
        raise SetupError("입력한 토큰이 지정한 봇의 토큰과 일치하지 않습니다.")
    chat_id = find_private_chat(api(token, "getUpdates"), username)
    # One vault write keeps the pair together. No plaintext file is created.
    try:
        vault.set_password(SERVICE, ACCOUNT, json.dumps({"bot_token": token, "chat_id": chat_id}))
    except Exception:
        raise SetupError("Windows 자격 증명 저장에 실패했습니다.") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="텔레그램 개인 알림 대화방을 안전하게 등록합니다.")
    parser.add_argument("--bot-username", required=True, help="봇 사용자 이름 (@ 제외)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.bot_username):
        print("봇 사용자 이름 형식이 올바르지 않습니다.")
        return 1
    if sys.platform != "win32" or not sys.stdin.isatty():
        print("본인 Windows PowerShell 또는 CMD 창에서 직접 실행하세요.")
        return 1
    try:
        # Explicit Windows backend: never accept a plaintext keyring fallback.
        from keyring.backends.Windows import WinVaultKeyring

        vault = WinVaultKeyring()
        if vault.get_password(SERVICE, ACCOUNT) is not None:
            if input("기존 텔레그램 등록을 교체할까요? yes 입력: ").strip() != "yes":
                print("기존 등록을 유지했습니다.")
                return 0
        print("저장해 둔 BotFather 토큰을 붙여넣고 Enter를 누르세요. 입력은 표시되지 않습니다.")
        token = getpass.getpass("봇 토큰: ")
        print("봇과 개인 대화방을 확인하는 중입니다…")
        register(token, args.bot_username, vault)
        print("등록 완료: 토큰과 개인 대화방 ID를 Windows 자격 증명 저장소에 저장했습니다.")
        print("AWS 연결은 다음 단계에서 진행합니다.")
        return 0
    except SetupError as exc:
        print(str(exc))
    except (KeyboardInterrupt, EOFError):
        print("입력을 취소했습니다.")
    except Exception:
        print("설정에 실패했습니다. Python 환경과 Windows 자격 증명 저장소를 확인하세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
