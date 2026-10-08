from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


class FormTransport(Protocol):
    def post_form(
        self,
        url: str,
        fields: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...


class UrllibFormTransport:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def post_form(
        self,
        url: str,
        fields: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            **(headers or {}),
        }
        request = Request(
            url,
            data=urlencode(fields).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Kakao API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Kakao API connection failed: {exc.reason}") from exc
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("Kakao API returned a non-object response")
        return payload


@dataclass(frozen=True, slots=True)
class KakaoSecret:
    rest_api_key: str
    refresh_token: str
    link_url: str
    client_secret: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KakaoSecret":
        required = ("rest_api_key", "refresh_token", "link_url")
        missing = [name for name in required if not str(payload.get(name, "")).strip()]
        if missing:
            raise RuntimeError(f"Kakao notification secret is missing: {', '.join(missing)}")
        link = str(payload["link_url"]).strip()
        if not link.startswith("https://"):
            raise RuntimeError("Kakao message link_url must use HTTPS")
        client_secret = str(payload.get("client_secret", "")).strip() or None
        return cls(
            rest_api_key=str(payload["rest_api_key"]).strip(),
            refresh_token=str(payload["refresh_token"]).strip(),
            link_url=link,
            client_secret=client_secret,
        )


class KakaoMemoNotifier:
    """Send a concise trade alert to the owner's KakaoTalk My Chatroom.

    Credentials stay in Secrets Manager. Each short-lived task refreshes an access
    token only when an alert is actually sent. If Kakao rotates the refresh token,
    the new value is persisted without exposing it to logs or message payloads.
    """

    def __init__(
        self,
        secrets_client,
        secret_arn: str,
        *,
        transport: FormTransport | None = None,
    ) -> None:
        if not secret_arn:
            raise ValueError("Kakao secret ARN is required")
        self.secrets_client = secrets_client
        self.secret_arn = secret_arn
        self.transport = transport or UrllibFormTransport()

    def send(self, subject: str, payload: dict[str, Any]) -> None:
        raw_secret = self._load_raw_secret()
        secret = KakaoSecret.from_dict(raw_secret)
        access_token, rotated_refresh_token = self._refresh_access_token(secret)
        if rotated_refresh_token and rotated_refresh_token != secret.refresh_token:
            raw_secret["refresh_token"] = rotated_refresh_token
            self.secrets_client.put_secret_value(
                SecretId=self.secret_arn,
                SecretString=json.dumps(raw_secret, ensure_ascii=False, sort_keys=True),
            )
        message = _render_trade_message(subject, payload, maximum_characters=200)
        template = {
            "object_type": "text",
            "text": message,
            "link": {"web_url": secret.link_url, "mobile_web_url": secret.link_url},
            "button_title": "기록 보기",
        }
        response = self.transport.post_form(
            KAKAO_MEMO_URL,
            {"template_object": json.dumps(template, ensure_ascii=False)},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.get("result_code") not in (0, "0"):
            raise RuntimeError(f"Kakao message failed: {response.get('msg', response)}")

    def _load_raw_secret(self) -> dict[str, Any]:
        response = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
        raw = response.get("SecretString")
        if not raw:
            raise RuntimeError("Kakao notification secret must be a JSON SecretString")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("Kakao notification secret must be a JSON object")
        return payload

    def _refresh_access_token(self, secret: KakaoSecret) -> tuple[str, str | None]:
        fields = {
            "grant_type": "refresh_token",
            "client_id": secret.rest_api_key,
            "refresh_token": secret.refresh_token,
        }
        if secret.client_secret:
            fields["client_secret"] = secret.client_secret
        response = self.transport.post_form(KAKAO_TOKEN_URL, fields)
        access_token = str(response.get("access_token", "")).strip()
        if not access_token:
            raise RuntimeError(f"Kakao token refresh failed: {response.get('error_description', response)}")
        rotated = str(response.get("refresh_token", "")).strip() or None
        return access_token, rotated


class TelegramNotifier:
    """Send free phone alerts through a private Telegram bot chat."""

    def __init__(
        self,
        secrets_client,
        secret_arn: str,
        *,
        transport: FormTransport | None = None,
    ) -> None:
        if not secret_arn:
            raise ValueError("Telegram secret ARN is required")
        self.secrets_client = secrets_client
        self.secret_arn = secret_arn
        self.transport = transport or UrllibFormTransport()

    def send(self, subject: str, payload: dict[str, Any]) -> None:
        response = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
        raw = response.get("SecretString")
        if not raw:
            raise RuntimeError("Telegram notification secret must be a JSON SecretString")
        secret = json.loads(raw)
        if not isinstance(secret, dict):
            raise RuntimeError("Telegram notification secret must be a JSON object")
        token = str(secret.get("bot_token", "")).strip()
        chat_id = str(secret.get("chat_id", "")).strip()
        if not token or not chat_id:
            raise RuntimeError("Telegram secret requires bot_token and chat_id")
        message = _render_trade_message(subject, payload, maximum_characters=4096)
        result = self.transport.post_form(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {
                "chat_id": chat_id,
                "text": message,
                "disable_notification": "false",
                "protect_content": "true",
            },
        )
        if result.get("ok") is not True:
            raise RuntimeError(f"Telegram message failed: {result.get('description', 'unknown error')}")


class SnsEmailNotifier:
    """Optional AWS SNS email fallback retained alongside messenger alerts."""

    def __init__(self, sns_client, topic_arn: str) -> None:
        if not topic_arn:
            raise ValueError("SNS topic ARN is required")
        self.sns_client = sns_client
        self.topic_arn = topic_arn

    def send(self, subject: str, payload: dict[str, Any]) -> None:
        self.sns_client.publish(
            TopicArn=self.topic_arn,
            Subject=subject[:100],
            Message=json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        )


def build_notifier(
    channel: str,
    secrets_client,
    secret_arn: str | None,
    *,
    sns_client=None,
    sns_topic_arn: str | None = None,
):
    normalized = channel.strip().lower()
    if normalized in {"", "disabled", "none"}:
        return None
    if normalized in {"email", "sns"}:
        if sns_client is None or not sns_topic_arn:
            raise RuntimeError("SNS client and topic ARN are required for email notifications")
        return SnsEmailNotifier(sns_client, sns_topic_arn)
    if not secret_arn:
        raise RuntimeError(f"notification secret ARN is required for {normalized}")
    if normalized == "telegram":
        return TelegramNotifier(secrets_client, secret_arn)
    if normalized == "kakao":
        return KakaoMemoNotifier(secrets_client, secret_arn)
    raise RuntimeError(f"unsupported notification channel: {channel}")


def _render_trade_message(
    subject: str,
    payload: dict[str, Any],
    *,
    maximum_characters: int,
) -> str:
    labels = (
        ("stock", "종목"),
        ("name", "종목"),
        ("code", "코드"),
        ("action", "구분"),
        ("entry_price", "매수가"),
        ("execution_price", "체결가"),
        ("quantity", "수량"),
        ("execution_quantity", "수량"),
        ("remaining_quantity", "잔여"),
        ("stop_price", "손절"),
        ("target1", "1차목표"),
        ("target2", "2차목표"),
        ("realized_pnl", "손익"),
        ("decided_at", "시각"),
        ("observed_at", "시각"),
    )
    lines = [subject.strip()]
    used_labels: set[str] = set()
    for key, label in labels:
        value = payload.get(key)
        if value in (None, "") or label in used_labels:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            rendered = f"{value:,}"
        else:
            rendered = str(value)
        lines.append(f"{label}: {rendered}")
        used_labels.add(label)
    text = "\n".join(lines)
    return text[:maximum_characters]
