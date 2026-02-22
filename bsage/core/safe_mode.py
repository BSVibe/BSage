"""SafeModeGuard — approval gate for dangerous skill execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import structlog

from bsage.core.exceptions import SafeModeError

logger = structlog.get_logger(__name__)


@dataclass
class ApprovalRequest:
    """Data passed to an ApprovalInterface when requesting user consent."""

    skill_name: str
    description: str
    action_summary: str
    connector_name: str | None = None


@runtime_checkable
class ApprovalInterface(Protocol):
    """Protocol that any approval UI (CLI, web, etc.) must implement."""

    async def request_approval(self, request: ApprovalRequest) -> bool: ...


class SafeModeGuard:
    """Gate that blocks dangerous skills unless the user explicitly approves.

    When *enabled* is False, all skills pass without approval.
    When *enabled* is True and a skill has ``is_dangerous=True``,
    the configured *interface* is asked for user consent.
    """

    def __init__(
        self,
        enabled: bool,
        interface: ApprovalInterface | None,
    ) -> None:
        self._enabled = enabled
        self._interface = interface

    async def check(self, skill_meta: Any) -> bool:
        """Return True if the skill is allowed to run.

        * Non-dangerous skills always pass.
        * When safe mode is disabled, all skills pass.
        * Dangerous skills require approval via the interface.
        * If no interface is configured for a dangerous skill, raises SafeModeError.
        """
        if not self._enabled:
            logger.info("safe_mode_disabled", skill=skill_meta.name)
            return True

        if not skill_meta.is_dangerous:
            logger.debug("safe_mode_pass", skill=skill_meta.name, dangerous=False)
            return True

        # Dangerous skill — need approval
        if self._interface is None:
            logger.error(
                "safe_mode_no_interface",
                skill=skill_meta.name,
            )
            raise SafeModeError(
                f"No approval interface configured for dangerous skill '{skill_meta.name}'"
            )

        request = ApprovalRequest(
            skill_name=skill_meta.name,
            description=skill_meta.description,
            action_summary=f"Execute dangerous skill '{skill_meta.name}' ({skill_meta.category})",
        )

        approved = await self._interface.request_approval(request)

        if approved:
            logger.info("safe_mode_approved", skill=skill_meta.name)
        else:
            logger.warning("safe_mode_rejected", skill=skill_meta.name)

        return approved
