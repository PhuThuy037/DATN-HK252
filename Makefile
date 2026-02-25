# ===== Docker =====

COMPOSE = docker compose
UID := $(shell id -u)
GID := $(shell id -g)

# ===== Variables =====
# Giá trị mặc định nếu quên truyền biến msg khi make revision
msg ?= "auto_migration"

# Start services (background)
up:
	$(COMPOSE) up -d

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

# Enter API container shell
shell:
	$(COMPOSE) exec -u $(UID):$(GID) api bash


# ===== Alembic =====

# Create new migration
# Usage: make revision msg="add_refresh_token"
revision:
	$(COMPOSE) exec -u $(UID):$(GID) api alembic revision --autogenerate -m "$(msg)"

# Apply latest migration
migrate:
	$(COMPOSE) exec -u $(UID):$(GID) api alembic upgrade head

# Rollback last migration
downgrade:
	$(COMPOSE) exec -u $(UID):$(GID) api alembic downgrade -1


# ===== Code =====

# Format code with Ruff
format:
	$(COMPOSE) exec -u $(UID):$(GID) api ruff format .

# Check and fix lint errors with Ruff
lint:
	$(COMPOSE) exec -u $(UID):$(GID) api ruff check . --fix

# Run tests
test:
	$(COMPOSE) exec -u $(UID):$(GID) api pytest

# Cleanup unused docker resources
clean:
	docker system prune -f