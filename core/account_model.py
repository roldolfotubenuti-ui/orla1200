"""Account data models and state definitions for TKS Engine multiaccount system."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AccountAuthStatus(str, Enum):
    """Strict lifecycle and authentication states as defined in TKS Engine Multiaccount specs."""
    IMPORTED = "IMPORTED"
    STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
    VALIDATING = "VALIDATING"
    AUTHENTICATED = "AUTHENTICATED"
    INVALID_SESSION = "INVALID_SESSION"
    EXPIRED = "EXPIRED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    DISABLED = "DISABLED"


@dataclass
class AccountRecord:
    """Represents a single registered multiaccount profile."""
    account_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    platform: str = "tiktok"
    cookie_file: str = ""
    department_id: str | None = None
    auth_status: str = AccountAuthStatus.IMPORTED.value
    enabled: bool = True
    imported_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    last_validated_at: str | None = None
    last_error: str | None = None
    cookie_count: int = 0
    display_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert record to JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountRecord:
        """Instantiate record safely from stored dictionary."""
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @property
    def display_name(self) -> str:
        """User-friendly display name."""
        if self.username and not self.username.startswith("Conta TikTok"):
            return f"@{self.username}"
        return self.display_title or self.username or "Conta não identificada"
