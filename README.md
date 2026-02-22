# ĐỒ ÁN TỐT NGHIỆP KỲ 252

## Tên đề tài

Phát triển công cụ ngăn chặn lộ thông tin riêng tư khi sử dụng chatbot

---

## Thông tin hướng dẫn

| Vai trò              | Họ tên             | Liên hệ                     |
|----------------------|--------------------|-----------------------------|
| Giảng viên hướng dẫn | ThS. Lê Đình Thuận | thuanle@hcmut.edu.vn        |
| Sinh viên thực hiện  | Nguyễn Phú Thụy    | thuy.nguyen113@hcmut.edu.vn |

---

## 1. Giới thiệu

Đề tài xây dựng một hệ thống AI Compliance nhằm phát hiện và ngăn chặn dữ liệu nhạy cảm trước khi gửi đến chatbot AI,
đồng thời ghi log và audit đầy đủ để phục vụ kiểm soát rủi ro trong môi trường cá nhân và doanh nghiệp.

---

## 2. Kiến trúc hệ thống

Backend sử dụng:

- FastAPI
- SQLModel và PostgreSQL
- Alembic Migration
- JWT Authentication
- Docker

---

## 3. Kiến trúc đa tenant và 2 scope chat

Các bảng chính:

- users
- companies
- company_members
- conversations
- messages
- rules

Hai phạm vi chat:

- Personal Chat: company_id = NULL
- Company Chat: company_id = UUID

---

## 4. Hệ thống Chat và Audit

Mỗi message lưu các trường phục vụ kiểm tra và truy vết:

- content
- content_hash
- content_masked
- decision_action
- risk_score
- ambiguous
- matched_rule_ids
- entities_json
- rag_evidence_json
- latency_ms
- sequence_number

sequence_number được sử dụng để:

- Đảm bảo thứ tự tin nhắn chính xác
- Tránh race condition khi gửi nhiều request đồng thời
- Hỗ trợ truy vấn lịch sử và phục vụ RAG

---

## 5. Authentication và Authorization

Authentication:

- JWT Access Token (sub = UUID, type = access)
- Refresh Token lưu trong cơ sở dữ liệu (hash SHA256)
- Cơ chế rotate refresh token

Authorization gồm 2 scope:

- Personal: chỉ Owner được truy cập
- Company: CompanyMember (member hoặc company_admin)

---

## 6. Scan Engine (AI Compliance Pipeline)

Pipeline xử lý trước khi lưu message:

User Input  
→ Regex Detector (VN custom)  
→ Presidio Detector  
→ Security Detector (Prompt Injection)  
→ Policy Engine  
→ ALLOW / MASK / BLOCK  
→ Lưu message và các trường audit

---

## 7. Tính năng chính

- Hệ thống chat đa tenant
- Ngăn chặn lộ thông tin nhạy cảm
- Mask dữ liệu tự động
- Phát hiện prompt injection
- Lưu audit đầy đủ
- Hỗ trợ rule theo company
- Mở rộng tích hợp RAG

---

## 8. Hướng dẫn chạy project

Chạy Docker:

make build

Chạy migration:

make migrate

Truy cập Swagger (API docs):

http://localhost:8000/docs#/default

---

## 9. Định hướng mở rộng

- Giao diện quản lý rule cho admin
- Kiểm tra trùng rule bằng embedding
- RAG hỗ trợ phát hiện nội dung mơ hồ
- Dashboard giám sát rủi ro
- Hệ thống cảnh báo thời gian thực

---

## Kết luận

Hệ thống đóng vai trò lớp bảo vệ trung gian giữa người dùng và chatbot AI, giúp giảm thiểu nguy cơ rò rỉ thông tin nhạy
cảm trong môi trường cá nhân và doanh nghiệp.