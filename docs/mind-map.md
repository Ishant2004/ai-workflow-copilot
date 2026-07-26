# Mind map

How the pieces of the Workflow AI Copilot connect — the mental model behind the build.

```mermaid
mindmap
  root((Workflow AI Copilot))
    Intent
      Plain-English task
      Parse goal
      Constraints and schedule
    Planning
      LLM: Claude
      Intent to steps
      Typed steps
      Dependencies
      Tool/function calling
    Execution
      Orchestrator
      Tools
        Web search
        Scrape
        Summarize
        Notify Slack/Email
      Queue + workers
      Retries
    Memory & grounding
      Postgres
      pgvector embeddings
      RAG over user docs
      Run history
    Human in the loop
      Approve
      Edit
      Reject
      Feedback loop
    Ops
      Docker
      Render (free) / any host
      Worker-free cron
      Logging & observability
      Evaluation
```

## The mental model in one paragraph

A user's sentence is an **intent**. The **planner** (Claude) turns that intent into
a structured **plan** of typed **steps**. The **orchestrator** runs each step by
invoking **tools**, recording everything as a **run**. Anything side-effecting waits
for a **human review**. Over time, uploaded documents (**RAG**) ground the answers,
and **feedback** sharpens future plans. Everything is observable and re-runnable.

## Key learning threads (map to AI/ML concepts)

- **Prompt engineering** → the planner and summarizer prompts.
- **Function/tool calling** → how Claude selects and parameterizes tools.
- **RAG + embeddings** → grounding workflows in uploaded docs (pgvector).
- **Agent orchestration** → multi-step planning and execution; later multi-agent.
- **Evaluation** → measuring plan/result quality, reducing hallucination.

## Glossary

- **Workflow** — a goal + its structured plan.
- **Step** — one typed unit of work (search, summarize, notify…).
- **Run** — one recorded execution of a workflow.
- **Tool** — a backend capability the planner can invoke.
- **Planner** — the LLM component that turns intent into steps.
- **Orchestrator** — code that executes steps and records results.
