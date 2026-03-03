# Privacy Guard Chat System - Architecture

## 1. Overview

This system is a multi-tenant AI chat platform with built-in:

- PII detection
- Prompt injection defense
- RAG-based policy verification
- Rule-based decision engine
- Masking / Blocking enforcement
- Multi-provider LLM support (Gemini + Ollama)

It is designed to prevent private data leakage when using chatbots.

---

# 2. High-Level Flow

User Message
    ↓
Scan Engine (Local + Presidio + Security)
    ↓
Context Scoring
    ↓
Security Injection Detection
    ↓
Conditional RAG (Policy Verifier)
    ↓
Rule Engine Evaluation
    ↓
Decision Resolver
    ↓
Final Action: ALLOW | MASK | BLOCK
    ↓
Persist Message
    ↓
(If allowed) → LLM Call
    ↓
Assistant Scan (same pipeline)
    ↓
Persist Assistant Message

---

# 3. Core Modules

## 3.1 Conversation Service

File: `app/conversation/service.py`

Responsibilities:

- Create personal/company conversation
- Append user message
- Call Scan Engine
- Call ChatService (LLM)
- Scan assistant reply
- Persist both messages
- Return `assistant_message_id` in send-message response contract

Two entry points:

- append_user_message_async() → Used by FastAPI async route
- append_user_message() → Sync wrapper (CLI / script use)

---

## 3.2 Scan Engine

File: `app/decision/scan_engine_local.py`

Pipeline:

1. Local regex detector
2. Spoken number detector
3. Presidio detector
4. Entity normalization
5. Entity merge
6. Context scoring
7. Security injection detection
8. Conditional RAG verification
9. Rule engine evaluation
10. Decision resolver

Returns:

{
  entities,
  signals,
  matches,
  final_action,
  latency_ms,
  risk_score,
  ambiguous
}

---

## 3.3 RAG Layer

Files:
- rag_verifier.py
- policy_retriever.py

Responsibilities:

- Embed user query
- Retrieve top-k policy chunks
- Call LLM to decide
- Log retrieval evidence
- Store structured decision

Embedding cache:
- Redis
- Key format: rag:emb:{model}:{sha256(text)}
- TTL: 7 days

---

## 3.4 Chat Service

File: `app/chat/service.py`

Supports:

- Gemini (Google AI Studio)
- Ollama (local)
- System prompt resolution: company prompt -> default prompt

Dynamic model routing:

If model_name starts with "gemini-" → GeminiProvider  
Else → OllamaProvider

Fallback behavior:

Primary fails → try secondary  
Both fail → return safe message

---

## 3.5 Multi-Tenant Design

Conversation types:

- Personal (company_id = NULL)
- Company-level (company_id != NULL)

Company conversation requires active CompanyMember.

Future strict RAG filter will isolate policy chunks per company.

---

# 4. Security Layers

1. Prompt Injection Detection
2. Exfiltration Pattern Detection
3. PII Detection (Phone, Email, Tax ID, CCCD, Credit Card)
4. Rule Layering
5. RAG Policy Reinforcement
6. Assistant Output Re-Scan

System is zero-trust toward model output.

---

# 5. Message Persistence Model

Each message stores:

- content (or NULL if blocked)
- content_masked
- final_action
- risk_score
- ambiguous flag
- matched_rule_ids
- entities_json
- latency_ms

Assistant messages go through same scan pipeline.

---

# 6. Design Principles

- Fail-safe over fail-open
- Model output never trusted
- RAG is assistive, not authoritative
- Rules override LLM when conflict
- Company isolation is mandatory (future strict mode)

---

# 7. Known Tradeoffs

- Sync DB session inside async flow
- No streaming response yet
- RAG timeout currently 10–15s
- No company-specific rule layering (planned)

---

End of architecture.
