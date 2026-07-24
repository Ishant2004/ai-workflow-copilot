"""Live notification tools — real Slack and email delivery.

These are the side-effecting tools that run *after* the human-in-the-loop review
gate (Step 10). They consume the reviewed summary from the execution context.
Selected via the registry when ``TOOLS_PROVIDER=live`` and the relevant delivery
config is present; otherwise the simulated fake is used.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.models.enums import StepType
from app.models.workflow import Step
from app.tools.base import ExecutionContext, Tool, ToolError, ToolOutput

logger = logging.getLogger(__name__)


def _message_from_context(step: Step, context: ExecutionContext) -> str:
    summarize = context.get(StepType.summarize.value) or {}
    summary = summarize.get("summary") if isinstance(summarize, dict) else None
    if not summary:
        # Fall back to the multi-agent orchestrator's reviewed final digest.
        orchestrate = context.get(StepType.orchestrate.value) or {}
        summary = orchestrate.get("final") if isinstance(orchestrate, dict) else None
    return summary or str(step.config.get("message") or step.name)


class LiveSlackNotifyTool(Tool):
    """Post a message to Slack via an incoming webhook.

    Incoming webhooks deliver to the channel the webhook was created for; the
    step's ``channel`` config is recorded but not used for routing.
    """

    def __init__(self, webhook_url: str, timeout_seconds: float) -> None:
        self._webhook_url = webhook_url
        self._timeout = timeout_seconds

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        message = _message_from_context(step, context)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json={"text": message})
        except httpx.HTTPError as exc:
            raise ToolError(f"Slack request failed: {exc}") from exc
        if resp.status_code != httpx.codes.OK:
            raise ToolError(f"Slack returned {resp.status_code}: {resp.text[:200]}")
        return {
            "delivered": True,
            "channel": str(step.config.get("channel") or "(webhook default)"),
            "message": message[:280],
        }


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    sender: str
    user: str | None = None
    password: str | None = None


class LiveEmailNotifyTool(Tool):
    """Send an email via SMTP (STARTTLS)."""

    def __init__(self, config: SmtpConfig, timeout_seconds: float) -> None:
        self._config = config
        self._timeout = timeout_seconds

    async def run(self, step: Step, context: ExecutionContext) -> ToolOutput:
        recipient = step.config.get("to")
        if not recipient:
            raise ToolError("notify_email requires a 'to' address in the step config")
        subject = str(step.config.get("subject") or "Workflow digest")
        body = _message_from_context(step, context)

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._config.sender
        message["To"] = str(recipient)
        message.set_content(body)

        try:
            # smtplib is blocking — run it off the event loop.
            await asyncio.to_thread(self._send, message)
        except (smtplib.SMTPException, OSError) as exc:
            raise ToolError(f"email send failed: {exc}") from exc
        return {"delivered": True, "to": str(recipient), "subject": subject}

    def _send(self, message: EmailMessage) -> None:
        cfg = self._config
        with smtplib.SMTP(cfg.host, cfg.port, timeout=self._timeout) as server:
            server.starttls(context=ssl.create_default_context())
            if cfg.user and cfg.password:
                server.login(cfg.user, cfg.password)
            server.send_message(message)
