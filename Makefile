# ===== Docker =====

COMPOSE = docker compose

ifeq ($(OS),Windows_NT)
EXEC_USER :=
else
UID := $(shell id -u)
GID := $(shell id -g)
EXEC_USER := -u $(UID):$(GID)
endif

# ===== Variables =====
# Giá trị mặc định nếu quên truyền biến msg khi make revision
msg ?= "auto_migration"
run ?= seed_rule

# Start services (background)
up:
	$(COMPOSE) up -d

upp:
	cd sentinel-ui && npm run dev

# Rebuild image + start
build:
	$(COMPOSE) up --build -d

# Stop services (keep DB data)
down:
	$(COMPOSE) down

# Reset database (⚠ delete volume)
reset-db:
	$(COMPOSE) down -v
	$(COMPOSE) up -d


# ===== Debug =====

# View API logs
logs:
	$(COMPOSE) logs -f api

logs-worker:
	$(COMPOSE) logs -f policy-worker

# Enter API container shell
shell:
	$(COMPOSE) exec $(EXEC_USER) api bash


# ===== Alembic =====

# Create new migration
# Usage: make revision msg="add_refresh_token"
revision:
	$(COMPOSE) exec $(EXEC_USER) api alembic revision --autogenerate -m "$(msg)"

# Apply latest migration
migrate:
	$(COMPOSE) exec $(EXEC_USER) api alembic upgrade head

# Rollback last migration
downgrade:
	$(COMPOSE) exec $(EXEC_USER) api alembic downgrade -1

# Run seed data
seed:
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.$(run)

list-scripts:
	ls app/script/*.py | xargs -n 1 basename | sed 's/\.py//'


# ===== Code =====

# Format code with Ruff
format:
	$(COMPOSE) exec $(EXEC_USER) api ruff format .

# Check and fix lint errors with Ruff
lint:
	$(COMPOSE) exec $(EXEC_USER) api ruff check . --fix

# Run tests
test:
	$(COMPOSE) exec $(EXEC_USER) api pytest

# Cleanup unused docker resources
clean:
	docker system prune -f

seed-all:
	$(COMPOSE) exec $(EXEC_USER) api alembic upgrade head
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.seed_context_terms
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.seed_rule
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.seed_policy_docs
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.seed_policy_chunks
	$(COMPOSE) exec -e UV_CACHE_DIR=/tmp/.uv_cache $(EXEC_USER) api uv run python -m app.script.seed_policy_chunk_embeddings
