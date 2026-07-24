"""Deterministic, offline multi-agent orchestrator.

Simulates the researcher → summarizer → reviewer collaboration with pure string
transforms — no network or API key — while preserving real data flow between the
agents so an orchestrated run is meaningful and testable. Selected by default and
whenever the live provider is unavailable.
"""

from __future__ import annotations

from app.agents.base import AgentOrchestrator, AgentRole, AgentTurn, OrchestrationResult


class FakeAgentOrchestrator(AgentOrchestrator):
    def __init__(self, review_rounds: int) -> None:
        self._review_rounds = max(0, review_rounds)

    async def run(self, topic: str, material: list[str]) -> OrchestrationResult:
        turns: list[AgentTurn] = []

        # Researcher: organize the supplied material (or note its absence).
        findings = [m.strip() for m in material if m and m.strip()]
        if findings:
            research = f"Findings on {topic}:\n" + "\n".join(f"- {f}" for f in findings)
        else:
            research = f"Findings on {topic}:\n- No source material supplied; based on the topic."
        turns.append(AgentTurn(AgentRole.researcher, research))

        # Summarizer: distill the findings into a short draft.
        draft = f"Summary of {topic}:\n" + "\n".join(
            f"- {line}" for line in research.splitlines()[1:]
        )
        turns.append(AgentTurn(AgentRole.summarizer, draft))

        # Reviewer: critique and improve the draft over N rounds.
        current = draft
        for round_no in range(1, self._review_rounds + 1):
            current = f"{current}\n\n(Reviewed for accuracy and completeness — round {round_no}.)"
            turns.append(
                AgentTurn(
                    AgentRole.reviewer,
                    f"Round {round_no}: draft is accurate and covers the topic; finalized.",
                )
            )

        return OrchestrationResult(
            topic=topic,
            final=current,
            turns=turns,
            review_rounds=self._review_rounds,
        )
