"""Live notification tool tests — Slack (mocked httpx) and email (mocked SMTP)."""

import asyncio

import httpx
import pytest
from app.config import Settings
from app.models.enums import StepType
from app.models.workflow import Step
from app.tools import ToolError, build_tool_registry
from app.tools.fake import FakeNotifyTool
from app.tools.notify import LiveEmailNotifyTool, LiveSlackNotifyTool, SmtpConfig

pytestmark = pytest.mark.unit

_CTX = {StepType.summarize.value: {"summary": "the digest body"}}


def _step(step_type: StepType, **config) -> Step:
    return Step(order_index=0, type=step_type, name=step_type.value, config=config)


# --- Slack ---


def test_slack_posts_message_to_webhook(monkeypatch):
    captured = {}

    async def fake_post(self, url, json=None, **kwargs):
        captured["url"] = url
        captured["text"] = json["text"]
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    tool = LiveSlackNotifyTool("https://hooks.slack.test/abc", timeout_seconds=5)
    out = asyncio.run(tool.run(_step(StepType.notify_slack, channel="#news"), _CTX))

    assert out["delivered"] is True
    assert captured["url"] == "https://hooks.slack.test/abc"
    assert captured["text"] == "the digest body"


def test_slack_raises_on_non_200(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        return httpx.Response(500, text="boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    tool = LiveSlackNotifyTool("https://hooks.slack.test/abc", timeout_seconds=5)
    with pytest.raises(ToolError):
        asyncio.run(tool.run(_step(StepType.notify_slack), _CTX))


# --- Email ---


def _email_tool() -> LiveEmailNotifyTool:
    return LiveEmailNotifyTool(
        SmtpConfig(host="smtp.test", port=587, sender="bot@test"),
        timeout_seconds=5,
    )


def test_email_sends_via_smtp(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        LiveEmailNotifyTool,
        "_send",
        lambda self, msg: sent.update(to=msg["To"], subj=msg["Subject"]),
    )
    out = asyncio.run(
        _email_tool().run(_step(StepType.notify_email, to="me@test", subject="Digest"), _CTX)
    )
    assert out["delivered"] is True
    assert sent["to"] == "me@test"
    assert sent["subj"] == "Digest"


def test_email_requires_recipient():
    with pytest.raises(ToolError):
        asyncio.run(_email_tool().run(_step(StepType.notify_email), _CTX))


def test_email_wraps_smtp_errors(monkeypatch):
    import smtplib

    def boom(self, msg):
        raise smtplib.SMTPException("nope")

    monkeypatch.setattr(LiveEmailNotifyTool, "_send", boom)
    with pytest.raises(ToolError):
        asyncio.run(_email_tool().run(_step(StepType.notify_email, to="me@test"), _CTX))


# --- registry wiring ---


def test_live_registry_uses_live_notifiers_when_configured():
    settings = Settings(
        tools_provider="live",
        slack_webhook_url="https://hooks.slack.test/abc",
        smtp_host="smtp.test",
        email_from="bot@test",
    )
    registry = build_tool_registry(settings)
    assert isinstance(registry.get(StepType.notify_slack), LiveSlackNotifyTool)
    assert isinstance(registry.get(StepType.notify_email), LiveEmailNotifyTool)


def test_live_registry_falls_back_to_fake_without_config():
    registry = build_tool_registry(Settings(tools_provider="live"))
    assert isinstance(registry.get(StepType.notify_slack), FakeNotifyTool)
    assert isinstance(registry.get(StepType.notify_email), FakeNotifyTool)
