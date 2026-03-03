# Roadmap - Next Phase Development

Current Status:
Core chat + scan + RAG working.

---

# Phase 1 - Stabilization

[ ] Add structured logging for:
    - Scan latency
    - RAG latency
    - LLM latency

[x] Add assistant_message_id to response contract

[x] Add system prompt support (company configurable)

[ ] Add timeout fail-fast for RAG (max 8s)

---

# Phase 2 - Multi-Tenant Strict Mode

[ ] Filter PolicyChunk by:
    company_id IN (NULL, current_company)

[ ] Company-specific rule layering:
    global rules
    + company rules
    priority resolution

[ ] Company audit log table:
    - user_id
    - message_id
    - action
    - risk_score
    - timestamp

---

# Phase 3 - Performance

[ ] Redis caching:
    - Embeddings (done)
    - RAG results cache (next)

[ ] Remove double cosine distance query (optimize SQL)

[ ] Add index for embedding search

[ ] Introduce background task for LLM (optional)

---

# Phase 4 - Production Hardening

[ ] Streaming support
[ ] Rate limiting per company
[ ] Admin dashboard
[ ] Alert when BLOCK spikes
[ ] Monitoring (Prometheus)

---

# Phase 5 - Advanced Features

[ ] Role-based policy (admin/dev/user persona policy)
[ ] Risk scoring ML layer
[ ] Adaptive policy tuning
[ ] Model ensemble for decision validation
[ ] Real-time moderation feedback loop

---

# Long-Term Vision

Build a privacy firewall layer for enterprise LLM usage.

Not just a chatbot.
A policy enforcement layer between user and AI.

---

End of roadmap.
