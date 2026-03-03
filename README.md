# ĐỒ ÁN TỐT NGHIỆP KỲ 252

## Tên đề tài

Phát triển công cụ ngăn chặn lộ thông tin riêng tư khi sử dụng chatbot

---

## Thông tin hướng dẫn

| Vai trò | Họ tên | Liên hệ |
|---|---|---|
| Giảng viên hướng dẫn | ThS. Lê Đình Thuận | thuanle@hcmut.edu.vn |
| Sinh viên thực hiện | Nguyễn Phú Thụy | thuy.nguyen113@hcmut.edu.vn |

---

## 1. Giới thiệu

Đề tài xây dựng một hệ thống AI Compliance nhằm phát hiện và ngăn chặn dữ liệu nhạy cảm trước khi gửi đến chatbot AI, đồng thời ghi log và audit đầy đủ để phục vụ kiểm soát rủi ro trong môi trường cá nhân và doanh nghiệp.

---

## 2. Tính năng hiện có

- Xác thực đầy đủ: register, login, refresh, logout, `GET /v1/auth/me`
- Company/Member (MVP):
  - Tạo company (tự động gán người tạo là `company_admin`)
  - Danh sách company của tôi
  - Thêm member theo email
  - Danh sách/cập nhật member (role, status)
  - Chặn demote/remove admin cuối cùng
- Company system prompt:
  - Quy tắc: `company_prompt > default_prompt`
  - API GET/PUT system prompt theo công ty (chỉ `company_admin`)
- Conversation:
  - Personal chat và company chat
  - `POST /messages` trả thêm `assistant_message_id`
  - `GET /messages` contract tối giản cho frontend + keyset pagination
- Scan pipeline:
  - Local regex + spoken number + Presidio + security injection
  - Rule engine + RAG verifier (conditional)
  - Re-scan output của assistant trước khi lưu

---

## 3. Tech Stack

- **Backend API:** FastAPI
- **ORM/Model:** SQLModel + SQLAlchemy
- **Database:** PostgreSQL
- **Migration:** Alembic
- **Authentication:** JWT (access token) + refresh token rotation
- **PII/Security Scan:** Local Regex, Spoken Number Detector, Microsoft Presidio, Prompt Injection Detector
- **Policy & Decision:** Rule Engine + Decision Resolver
- **RAG:** Policy retrieval + verifier + Redis embedding cache
- **LLM Provider:** Gemini API, Ollama
- **Container:** Docker + Docker Compose
- **Build/Ops command:** Makefile

---

## 4. Kiến trúc đa tenant và 2 scope chat

Các bảng chính:
- `users`
- `companies`
- `company_members`
- `conversations`
- `messages`
- `rules` + các bảng RAG

Hai phạm vi chat:
- Personal Chat: `company_id = NULL`
- Company Chat: `company_id = UUID`

---

## 5. Hệ thống Chat và Audit

Mỗi message lưu các trường phục vụ kiểm tra và truy vết:
- `content`
- `content_hash`
- `content_masked`
- `final_action`
- `risk_score`
- `ambiguous`
- `matched_rule_ids`
- `entities_json`
- `rag_evidence_json`
- `latency_ms`
- `sequence_number`

`sequence_number` được sử dụng để:
- Đảm bảo thứ tự tin nhắn chính xác
- Tránh race condition khi gửi nhiều request đồng thời
- Hỗ trợ truy vấn lịch sử và phục vụ phân trang keyset

---

## 6. Authentication và Authorization

Authentication:
- JWT Access Token (`sub = UUID`, `type = access`)
- Refresh Token lưu trong cơ sở dữ liệu (hash)
- Cơ chế rotate refresh token

Authorization gồm 2 scope:
- Personal: chỉ owner được truy cập
- Company: yêu cầu `CompanyMember` active (member hoặc company_admin tùy API)

---

## 7. Scan Engine (AI Compliance Pipeline)

Pipeline xử lý trước khi lưu/trả message:

User Input
-> Regex Detector (VN custom)
-> Spoken Number Detector
-> Presidio Detector
-> Security Detector (Prompt Injection)
-> Rule Engine + Conditional RAG
-> ALLOW / MASK / BLOCK
-> Lưu message và các trường audit

Assistant output cũng đi qua pipeline scan tương tự trước khi trả về.

---

## 8. API chính

### Auth
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `GET /v1/auth/me`

### Company
- `POST /v1/companies`
- `GET /v1/companies/me`
- `GET /v1/companies/{company_id}`
- `POST /v1/companies/{company_id}/members`
- `GET /v1/companies/{company_id}/members`
- `PATCH /v1/companies/{company_id}/members/{member_id}`

### Company settings
- `GET /v1/companies/{company_id}/settings/system-prompt`
- `PUT /v1/companies/{company_id}/settings/system-prompt`

### Conversation
- `POST /v1/conversations/personal`
- `POST /v1/companies/{company_id}/conversations`
- `POST /v1/conversations/{conversation_id}/messages`
- `GET /v1/conversations/{conversation_id}/messages?limit=20&before_seq=...`

---

## 9. Contract GET messages (frontend-safe)

Response `data`:
- `items`: danh sách message tối giản
  - `id`, `role`, `content`, `created_at`, `state`
- `page`: thông tin pagination
  - `limit`, `has_more`, `next_before_seq`, `oldest_seq`, `newest_seq`

`state` gồm:
- `normal`
- `masked`
- `blocked`

---

## 10. Hướng dẫn chạy project

### Yêu cầu môi trường
- Docker + Docker Compose
- Make
- Cấu hình LLM/Embedding:
  - `CHAT_PROVIDER=gemini` -> bắt buộc có `GOOGLE_API_KEY`
  - `CHAT_PROVIDER=ollama` -> Ollama phải chạy và có model chat tương ứng (`OLLAMA_MODEL`)
  - Model chat mặc định khuyến nghị: `OLLAMA_MODEL=qwen2.5:7b`
  - Để seed và chạy RAG embeddings, cần Ollama model `mxbai-embed-large`

### Cài mới từ đầu

1. Clone repo và vào thư mục dự án
2. Tạo file env:
```bash
cp .env.example .env
```
3. Build + up service:
```bash
make build
```
4. Chạy migration:
```bash
make migrate
```
5. Seed dữ liệu đầy đủ (rule + policy docs + chunks + embeddings):
```bash
make seed-all
```
6. Truy cập Swagger:
- http://localhost:8000/docs

### Cài lại (reset full)

Nếu cần làm sạch DB và cài lại:
```bash
make reset-db
make migrate
make seed-all
```

Nếu chỉ muốn seed rule nhanh (không seed full RAG):
```bash
make seed run=seed_rule
```

---

## 11. Ghi chú seed rule

`app/script/seed_rule.py` đã bỏ hardcode `PREFERRED_USER_ID`.
Thứ tự resolve `created_by`:
1. `SEED_RULE_CREATED_BY_EMAIL` (nếu có)
2. User active đầu tiên trong DB
3. Nếu DB chưa có user active và `SEED_RULE_AUTO_CREATE_USER=true` (mặc định), tự tạo seed user

Các env liên quan:
- `SEED_RULE_CREATED_BY_EMAIL`
- `SEED_RULE_AUTO_CREATE_USER`
- `SEED_RULE_USER_EMAIL`
- `SEED_RULE_USER_PASSWORD`
- `SEED_RULE_USER_NAME`

---

## 12. Định hướng mở rộng

- Dashboard quản trị rule và policy
- Multi-tenant strict mode cho RAG retrieval
- Logging/monitoring đầy đủ (latency scan/rag/llm)
- Streaming response
- Rate limiting theo company

---

## Kết luận

Hệ thống đóng vai trò lớp bảo vệ trung gian giữa người dùng và chatbot AI, giúp giảm thiểu nguy cơ rò rỉ thông tin nhạy cảm trong môi trường cá nhân và doanh nghiệp.
