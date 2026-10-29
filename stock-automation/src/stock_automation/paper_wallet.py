"""Paper wallet keys, with an optional epoch that starts a fresh ledger.

``PAPER_WALLET_EPOCH`` (e.g. ``200K-20261103``) appends ``#<epoch>`` to every
paper wallet key, so a new starting cash never reuses or overwrites an older
wallet. Without an epoch the keys are the original ones.

Standard library only: the web dashboard Lambda packages this file without the
rest of the program.
"""
from __future__ import annotations

import os
import re

WALLET_EPOCH_ENV = "PAPER_WALLET_EPOCH"
_EPOCH_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,40}")
# Session values match models.Session; a test keeps the two in step.
_CLOSING_SESSIONS = ("KRX_1520", "NXT_1955")
_STRATEGY_KEYS = (
    *(f"CLOSING_BET#{session}" for session in _CLOSING_SESSIONS),
    "DAY_TRADE",
    "MEDIUM_TERM",
)


def wallet_epoch(epoch: str | None = None) -> str:
    """Return the validated epoch; ``None`` reads ``PAPER_WALLET_EPOCH``."""
    value = (os.getenv(WALLET_EPOCH_ENV, "") if epoch is None else epoch).strip()
    if value and not _EPOCH_PATTERN.fullmatch(value):
        raise ValueError("PAPER_WALLET_EPOCH must be 1-40 letters, digits, '_' or '-'")
    return value


def wallet_key(strategy: str, session: str | None = None, *, epoch: str | None = None) -> str:
    """The paper wallet key of one strategy (and closing-bet session, e.g. ``Session.KRX_1520``)."""
    base = f"WALLET#{strategy}" + (f"#{getattr(session, 'value', session)}" if session else "")
    if base.removeprefix("WALLET#") not in _STRATEGY_KEYS:
        raise ValueError(f"unknown paper wallet: {base}")
    value = wallet_epoch(epoch)
    return f"{base}#{value}" if value else base


def is_current_wallet(key: str, *, epoch: str | None = None) -> bool:
    """True for a wallet row the runtime writes under the current epoch.

    A paper strategy wallet counts only with the current suffix (none without an
    epoch); wallets of other epochs are kept as history. Any other ``WALLET#``
    row is not a paper strategy wallet and counts as before the epoch existed.
    """
    if not key.startswith("WALLET#"):
        return False
    name = key.removeprefix("WALLET#")
    base = next((s for s in _STRATEGY_KEYS if name == s or name.startswith(s + "#")), None)
    if base is None:
        return True
    value = wallet_epoch(epoch)
    return name == (f"{base}#{value}" if value else base)


def stored_wallet_key(item: dict, legacy_key: str) -> str:
    """The wallet key saved on an open-position item; older items use ``legacy_key``."""
    stored = item.get("wallet_key", {}).get("S", "").strip()
    return stored or legacy_key
