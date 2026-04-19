from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional

from pydantic import BaseModel

from erasure.profile import UserProfile

Method = Literal["form", "email", "mail", "unknown"]


class Broker(ABC, BaseModel):
    name: str
    opt_out_url: Optional[str] = None
    method: Method = "unknown"
    requires_email_verify: bool = False
    requires_account: bool = False
    notes: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    async def search(self, profile: UserProfile) -> list[dict]:
        """Search the broker for records matching profile. Returns raw result dicts."""
        ...

    @abstractmethod
    async def opt_out(self, profile: UserProfile) -> bool:
        """Submit opt-out request. Returns True if submission succeeded."""
        ...

    @abstractmethod
    async def verify_email(self, token: str) -> bool:
        """Complete email verification step using the token from inbox. Returns True on success."""
        ...

    @abstractmethod
    async def check_status(self) -> str:
        """Return current removal status: 'pending', 'removed', 'failed', etc."""
        ...
