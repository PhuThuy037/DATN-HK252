FROM python:3.12-slim-bookworm

# Cài đặt uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --- BÍ QUYẾT Ở ĐÂY ---
# Ép uv phải dùng /opt/venv làm môi trường ảo thay vì /app/.venv mặc định
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
# Đưa venv vào PATH để gọi python, uvicorn, spacy trực tiếp
ENV PATH="/opt/venv/bin:$PATH"

# Copy CẢ 2 FILE này trước để tận dụng cache và giúp uv sync siêu tốc
COPY pyproject.toml uv.lock ./

# ---> THÊM DÒNG NÀY ĐỂ CẤP PIP CHO SPACY <---
RUN uv venv --seed

# Khởi tạo venv và cài package (nó sẽ tự chui vào /opt/venv nhờ cấu hình ở trên)
RUN uv sync --no-dev

# Bây giờ python đã thấy spacy, lệnh này sẽ chạy mượt mà!
RUN python -m spacy download en_core_web_sm

# Copy toàn bộ code vào
COPY . .

# Chạy server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]