from __future__ import annotations

import os
import platform
import sys
import ipaddress
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping

from .dart import DartClient


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    checks: tuple[DiagnosticCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in self.checks
            ],
        }


def diagnose(
    *,
    online: bool = False,
    aws: bool = False,
    environment: Mapping[str, str] | None = None,
    kiwoom_factory: Callable[[], object] | None = None,
    dart_factory: Callable[[str], object] | None = None,
    egress_probe: Callable[[], str] | None = None,
    write_probes: bool = False,
    test_notification: bool = False,
) -> DiagnosticReport:
    """Validate paper-only runtime configuration without exposing secret values."""
    env = environment if environment is not None else os.environ
    checks: list[DiagnosticCheck] = []
    checks.append(DiagnosticCheck(
        "python_version",
        sys.version_info >= (3, 13),
        f"{platform.python_version()} (required >=3.13)",
    ))
    mode = env.get("KIWOOM_MODE", "")
    checks.append(DiagnosticCheck(
        "paper_mode",
        mode == "demo",
        "KIWOOM_MODE=demo required; real mode is rejected",
    ))
    order_gate = env.get("KIWOOM_MCP_ALLOW_ORDERS", "").strip().lower()
    checks.append(DiagnosticCheck(
        "order_gate_disabled",
        order_gate not in {"1", "true", "yes", "on"} and env.get("LIVE_ORDER_ENABLED", "0") == "0",
        "live-order gate must remain disabled",
    ))
    app_key = env.get("APP_KEY_MOCK", "")
    app_secret = env.get("APP_SECRET_MOCK", "")
    dart_key = env.get("DART_API_KEY", "")
    checks.append(_presence("kiwoom_demo_credentials", app_key and app_secret))
    checks.append(DiagnosticCheck(
        "dart_api_key",
        len(dart_key) == 40,
        "configured" if len(dart_key) == 40 else "missing or not 40 characters",
    ))

    channel = env.get("NOTIFICATION_CHANNEL", "disabled").lower()
    valid_channels = {"telegram", "kakao", "email", "disabled"}
    checks.append(DiagnosticCheck(
        "notification_channel",
        channel in valid_channels,
        channel if channel in valid_channels else "unsupported channel",
    ))
    if aws:
        required = (
            "PAPER_BUCKET",
            "PAPER_TABLE",
            "TRADING_CALENDAR_KEY",
            "STARTING_CASH",
            "BUY_FEE_BPS",
            "SELL_FEE_BPS",
            "SELL_TAX_BPS",
        )
        missing = tuple(name for name in required if not env.get(name))
        checks.append(DiagnosticCheck(
            "aws_runtime_environment",
            not missing,
            "configured" if not missing else f"missing: {','.join(missing)}",
        ))
        notification_secret = env.get("NOTIFICATION_SECRET_ARN", "")
        notification_ok = channel in {"disabled", "email"} or bool(notification_secret)
        checks.append(DiagnosticCheck(
            "notification_secret",
            notification_ok,
            "configured or not required" if notification_ok else "messenger secret ARN missing",
        ))

    if online and aws:
        egress = _check_egress(env.get("EXPECTED_EGRESS_IP", ""), egress_probe)
        checks.append(egress)
        if not egress.ok:
            return DiagnosticReport(tuple(checks))

    if online and app_key and app_secret and mode == "demo":
        checks.append(_check_kiwoom(kiwoom_factory))
    elif online:
        checks.append(DiagnosticCheck(
            "kiwoom_read_probe", False, "skipped because demo credentials are invalid"
        ))
    if online and len(dart_key) == 40:
        checks.append(_check_dart(dart_key, dart_factory))
    elif online:
        checks.append(DiagnosticCheck(
            "dart_read_probe", False, "skipped because OpenDART key is invalid"
        ))
    if write_probes or test_notification:
        if not (online and aws and all(check.ok for check in checks)):
            checks.append(DiagnosticCheck("explicit_integration_probes", False, "healthy online AWS demo environment required"))
        else:
            from .integration_checks import notification_probe, storage_probes
            if write_probes:
                checks.extend(storage_probes(env))
            if test_notification and all(check.ok for check in checks):
                checks.append(notification_probe(env))
    return DiagnosticReport(tuple(checks))


def _check_egress(expected: str, probe: Callable[[], str] | None) -> DiagnosticCheck:
    try:
        expected_ip = ipaddress.IPv4Address(expected)
        if probe is None:
            with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=5) as response:
                observed = response.read(65).decode("ascii").strip()
        else:
            observed = probe().strip()
        matched = expected_ip == ipaddress.IPv4Address(observed)
        return DiagnosticCheck("fixed_egress", matched, "matches expected IP" if matched else "egress mismatch")
    except Exception as error:
        return DiagnosticCheck("fixed_egress", False, f"probe failed ({type(error).__name__})")


def _presence(name: str, value: object) -> DiagnosticCheck:
    return DiagnosticCheck(name, bool(value), "configured" if value else "missing")


def _check_kiwoom(factory: Callable[[], object] | None) -> DiagnosticCheck:
    try:
        if factory is None:
            from kiwoom import get_client

            client = get_client(mode="demo", timeout_seconds=20)
        else:
            client = factory()
        response = client.fetch_page(
            api_id="ka10099",
            path="/api/dostk/stkinfo",
            body={"mrkt_tp": "0"},
        )
        body = response.body
        ok = body.get("return_code") in (None, 0, "0") and isinstance(body.get("list"), list)
        detail = f"read probe returned {len(body.get('list', []))} listed rows" if ok else "read probe rejected"
        return DiagnosticCheck("kiwoom_read_probe", ok, detail)
    except Exception as exc:
        return DiagnosticCheck("kiwoom_read_probe", False, f"probe failed ({type(exc).__name__})")


def _check_dart(api_key: str, factory: Callable[[str], object] | None) -> DiagnosticCheck:
    try:
        client = factory(api_key) if factory else DartClient(api_key)
        count = len(client.corporation_codes())
        return DiagnosticCheck(
            "dart_read_probe",
            count > 0,
            f"corporation map returned {count} listed rows",
        )
    except Exception as exc:
        return DiagnosticCheck("dart_read_probe", False, f"probe failed ({type(exc).__name__})")
