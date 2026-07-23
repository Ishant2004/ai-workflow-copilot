AI project idea: Workflow AI Copilot

Build a web app where users can describe a repetitive task in plain English, and the system generates a multi-step workflow, executes parts of it, and learns from feedback.

What it does

A user can type something like:

“Every morning, collect the latest AI startup news, summarize it, and send me a digest on Slack.”

The AI copilot should:

Understand the intent and break it into steps

Search or scrape relevant sources

Summarize and structure the information

Schedule or trigger the workflow

Allow the user to approve, edit, or reject the result

Why this is a strong project

It combines LLMs, backend engineering, DevOps, and automation.

It demonstrates AI orchestration, not just prompt engineering.

You can talk about system design, scalability, retries, queues, and observability in interviews.

It aligns well with your current backend and AWS experience.

Tech stack

Layer

	

Technology




Frontend

	

Next.js + Tailwind




Backend

	

FastAPI or Node.js




LLM

	

OpenAI GPT-4o or open-source model




Vector DB

	

Qdrant, Pinecone, or pgvector




Queue

	

SQS, Redis, or Celery




Storage

	

PostgreSQL + S3




Deployment

	

Docker + AWS ECS/Lambda

AI/ML concepts you’ll learn

Prompt engineering — designing reliable prompts

Function calling / tool use — letting the model call APIs

RAG (Retrieval-Augmented Generation) — grounding responses in documents

Embeddings — semantic search over data

Agent orchestration — planning and executing multi-step tasks

Evaluation — measuring response quality and reducing hallucinations

Features to build in phases

MVP (2–3 weeks)

User enters a task description

LLM generates workflow steps

Execute simple actions: web search, summarization, email/Slack output

Store workflow history

Phase 2

Add RAG so workflows can use uploaded PDFs or company docs

Add a visual workflow editor (drag-and-drop nodes)

Add retries, logging, and error handling

Phase 3

Multi-agent collaboration (research agent, summarizer agent, reviewer agent)

Feedback loop so the AI improves workflow suggestions

Deploy with Docker, ECS/Lambda, and CI/CD