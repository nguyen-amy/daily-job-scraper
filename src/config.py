"""Load and validate environment-based configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    gmail_user: str
    gmail_app_password: str

    @property
    def recipient(self) -> str:
        # Sender and recipient are the same Gmail account.
        return self.gmail_user


def load() -> Config:
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    missing = [name for name, val in (("GMAIL_USER", user), ("GMAIL_APP_PASSWORD", pw)) if not val]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Set them locally or configure as GitHub Actions secrets."
        )
    return Config(gmail_user=user, gmail_app_password=pw)  # type: ignore[arg-type]
