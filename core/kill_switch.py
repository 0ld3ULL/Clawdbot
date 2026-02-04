"""
Emergency kill switch.

Can be activated via:
1. Telegram /kill command
2. KILL_FILE existence (survives restarts)
3. Budget critical threshold exceeded

When active, ALL agent activity stops immediately.
"""

import os
from datetime import datetime
from pathlib import Path


KILL_FILE = Path("data/.KILL_SWITCH")


class KillSwitch:

    def __init__(self):
        self._active = False
        # Check for persistent kill file on startup
        if KILL_FILE.exists():
            self._active = True

    @property
    def is_active(self) -> bool:
        """Check if kill switch is active (includes file check)."""
        if KILL_FILE.exists():
            self._active = True
        return self._active

    def activate(self, reason: str = "Manual kill"):
        """Activate kill switch. Stops ALL agent activity."""
        self._active = True
        KILL_FILE.parent.mkdir(parents=True, exist_ok=True)
        KILL_FILE.write_text(
            f"KILLED: {reason}\nTime: {datetime.now().isoformat()}\n",
            encoding="utf-8"
        )

    def deactivate(self):
        """Deactivate kill switch. Requires explicit action."""
        self._active = False
        if KILL_FILE.exists():
            KILL_FILE.unlink()

    def get_reason(self) -> str | None:
        """Get the reason the kill switch was activated."""
        if KILL_FILE.exists():
            content = KILL_FILE.read_text(encoding="utf-8")
            return content.strip()
        return None

    def check_or_raise(self):
        """Check kill switch; raise if active. Use as a gate."""
        if self.is_active:
            reason = self.get_reason() or "Unknown"
            raise KillSwitchActive(reason)


class KillSwitchActive(Exception):
    """Raised when an operation is attempted while kill switch is active."""
    pass
