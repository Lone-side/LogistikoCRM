.DEFAULT_GOAL := help

help: ## Εμφάνιση εντολών
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## 🚀 Εγκατάσταση + εκκίνηση dev server (SQLite, χωρίς Docker)
	@bash start_dev.sh

run: ## ▶️  Εκκίνηση dev server (μετά την πρώτη εγκατάσταση)
	@bash -c "source venv/bin/activate && python manage.py runserver 0.0.0.0:8000"

docker-dev: ## 🐳 Εκκίνηση με Docker (dev mode, χωρίς PostgreSQL)
	@docker compose -f docker-compose.dev.yml up

docker-prod: ## 🐳 Εκκίνηση με Docker (production: PostgreSQL + Redis)
	@cp -n .env.example .env 2>/dev/null || true
	@docker compose up -d
	@echo "Τρέχει στο http://localhost:8000"

stop: ## ⏹  Σταμάτημα Docker containers
	@docker compose down 2>/dev/null; docker compose -f docker-compose.dev.yml down 2>/dev/null; echo "Σταμάτησαν."

test: ## 🧪 Εκτέλεση tests
	@bash -c "source venv/bin/activate && python manage.py test tests -v 0"

migrate: ## 🗄  Εκτέλεση migrations
	@bash -c "source venv/bin/activate && python manage.py migrate"

shell: ## 🐍 Django shell
	@bash -c "source venv/bin/activate && python manage.py shell"

logs: ## 📋 Docker logs
	@docker compose logs -f 2>/dev/null || docker compose -f docker-compose.dev.yml logs -f

clean: ## 🧹 Καθαρισμός venv, cache, compiled files
	@rm -rf venv __pycache__ .pytest_cache db.sqlite3
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; echo "Καθαρίστηκε."

.PHONY: help dev run docker-dev docker-prod stop test migrate shell logs clean
