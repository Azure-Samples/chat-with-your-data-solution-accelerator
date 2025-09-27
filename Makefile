SHELL := /bin/bash

.PHONY: help
.DEFAULT_GOAL := help

AZURE_ENV_FILE := $(shell azd env list --output json | jq -r '.[] | select(.IsDefault == true) | .DotEnvPath')

ENV_FILE := .env
ifeq ($(filter $(MAKECMDGOALS),config clean),)
	ifneq ($(strip $(wildcard $(ENV_FILE))),)
		ifneq ($(MAKECMDGOALS),config)
			include $(ENV_FILE)
			export
		endif
	endif
endif

include $(AZURE_ENV_FILE)

help: ## 💬 This help message :)
	@grep -E '[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-23s\033[0m %s\n", $$1, $$2}'

ci: lint unittest unittest-frontend functionaltest ## 🚀 Continuous Integration (called by Github Actions)

lint: ## 🧹 Lint the code
	@echo -e "\e[34m$@\e[0m" || true
	@poetry run flake8 code

build-frontend: ## 🏗️ Build the Frontend webapp
	@echo -e "\e[34m$@\e[0m" || true
	@cd code/frontend && npm install && npm run build

python-test: ## 🧪 Run Python unit + functional tests
	@echo -e "\e[34m$@\e[0m" || true
	@poetry run pytest -m "not azure" $(optional_args)

unittest: ## 🧪 Run the unit tests
	@echo -e "\e[34m$@\e[0m" || true
	@poetry run pytest -vvv -m "not azure and not functional" $(optional_args)

unittest-frontend: build-frontend ## 🧪 Unit test the Frontend webapp
	@echo -e "\e[34m$@\e[0m" || true
	@cd code/frontend && npm run test

functionaltest: ## 🧪 Run the functional tests
	@echo -e "\e[34m$@\e[0m" || true
	@poetry run pytest code/tests/functional -m "functional"

uitest: ## 🧪 Run the ui tests in headless mode
	@echo -e "\e[34m$@\e[0m" || true
	@cd tests/integration/ui && npm install && npx cypress run --env ADMIN_WEBSITE_NAME=$(ADMIN_WEBSITE_NAME),FRONTEND_WEBSITE_NAME=$(FRONTEND_WEBSITE_NAME)

docker-compose-up: ## 🐳 Run the docker-compose file
	@cd docker && AZD_ENV_FILE=$(AZURE_ENV_FILE) docker-compose up

azd-login: ## 🔑 Login to Azure with azd and a SPN
	@echo -e "\e[34m$@\e[0m" || true
	@azd auth login --client-id ${AZURE_CLIENT_ID} --client-secret ${AZURE_CLIENT_SECRET} --tenant-id ${AZURE_TENANT_ID}

azd-login: ## 🔑 Login to Azure with azd and a SPN
	@echo -e "\e[34m$@\e[0m" || true
	@azd auth login --client-id ${AZURE_CLIENT_ID} --client-secret ${AZURE_CLIENT_SECRET} --tenant-id ${AZURE_TENANT_ID}

# Fixed Makefile section for deploy target
# Fixed Makefile section for deploy target
deploy: azd-login ## Deploy everything to Azure
	@echo -e "\e[34m$@\e[0m" || true
	@echo "AZURE_ENV_NAME: '${AZURE_ENV_NAME}'"
	@echo "AZURE_LOCATION: '${AZURE_LOCATION}'"
	@echo "AZURE_RESOURCE_GROUP: '${AZURE_RESOURCE_GROUP}'"

	# Validate required variables
	@if [ -z "${AZURE_ENV_NAME}" ]; then echo "❌ AZURE_ENV_NAME not set"; exit 1; fi
	@if [ -z "${AZURE_LOCATION}" ]; then echo "❌ AZURE_LOCATION not set"; exit 1; fi
	@if [ -z "${AZURE_RESOURCE_GROUP}" ]; then echo "❌ AZURE_RESOURCE_GROUP not set"; exit 1; fi

	@azd env new ${AZURE_ENV_NAME} --location ${AZURE_LOCATION}
	@azd env set AZURE_RESOURCE_GROUP ${AZURE_RESOURCE_GROUP}

	# Provision and deploy
	@azd provision --no-prompt
	@azd deploy web --no-prompt || true
	@azd deploy function --no-prompt || true
	@azd deploy adminweb --no-prompt
	@azd env get-values > .env.temp
	@cat .env.temp

	@sleep 30
	@azd show --output json > deploy_output.json || echo "{}" > deploy_output.json
	@echo "=== deploy_output.json contents ==="
	@cat deploy_output.json | jq . || cat deploy_output.json

	# Extract URLs
	@echo "=== Extracting URLs using multiple methods ==="
	@azd show 2>&1 | tee full_deployment_output.log
	@jq -r '.services.web?.project?.hostedEndpoints?[0]?.url // ""' deploy_output.json > frontend_url.txt || echo "" > frontend_url.txt
	@jq -r '.services.adminweb?.project?.hostedEndpoints?[0]?.url // ""' deploy_output.json > admin_url.txt || echo "" > admin_url.txt
	@grep -oE "https://app-[a-zA-Z0-9-]*\.azurewebsites\.net/" full_deployment_output.log | grep -v admin | head -1 >> frontend_url.txt || true
	@grep -oE "https://app-[a-zA-Z0-9-]*-admin\.azurewebsites\.net/" full_deployment_output.log | head -1 >> admin_url.txt || true
	@sort frontend_url.txt | uniq | grep -v '^$$' | head -1 > frontend_url_clean.txt && mv frontend_url_clean.txt frontend_url.txt || echo "" > frontend_url.txt
	@sort admin_url.txt | uniq | grep -v '^$$' | head -1 > admin_url_clean.txt && mv admin_url_clean.txt admin_url.txt || echo "" > admin_url.txt

	@echo "=== URL Extraction Results ==="
	@FRONTEND_URL=$$(cat frontend_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	ADMIN_URL=$$(cat admin_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	echo "Frontend URL: $$FRONTEND_URL"; \
	echo "Admin URL: $$ADMIN_URL"

	@echo "=== Final Deployment Status ==="
	@echo "Frontend URL:" && cat frontend_url.txt || echo "Not available"
	@echo "Admin URL:" && cat admin_url.txt || echo "Not available"
	@echo ""
	@echo "🚀 Deployment completed!"
	@echo "⏰ Authentication will be disabled via GitHub Actions pipeline."
	@echo "🔄 Check the pipeline logs for authentication disable status."
	@echo "=== Extracting PostgreSQL Host Endpoint ==="
		@azd env get-values > .env.temp 2>/dev/null || echo "" > .env.temp

		@PG_HOST_VAL=$$(grep '^AZURE_POSTGRESQL_HOST_NAME=' .env.temp | cut -d'=' -f2 | tr -d '"' | xargs); \
		if [ -z "$$PG_HOST_VAL" ]; then \
			echo "❌ PostgreSQL host not found in .env.temp. Using fallback localhost"; \
			PG_HOST_VAL="localhost"; \
		else \
			echo "✅ PostgreSQL host extracted from .env.temp: $$PG_HOST_VAL"; \
		fi; \
		echo "$$PG_HOST_VAL" > pg_host.txt





	@echo "=== PostgreSQL Configuration ==="
	@echo "Username: admintest (hardcoded)"
	@echo "Database: postgres (hardcoded)"
	@echo "Port: 5432 (hardcoded)"
	@echo "Host: $$(cat pg_host.txt 2>/dev/null || echo 'Not available')"
	@echo "Password: Initial_0524 (hardcoded)"

# Helper target to check current authentication status
check-auth:
	@echo "=== Checking Authentication Status ==="
	@FRONTEND_URL=$$(cat frontend_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	ADMIN_URL=$$(cat admin_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	if [ -n "$$FRONTEND_URL" ]; then \
		echo "Testing Frontend: $$FRONTEND_URL"; \
		HTTP_CODE=$$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$$FRONTEND_URL" 2>/dev/null || echo "000"); \
		echo "Frontend HTTP Status: $$HTTP_CODE"; \
	fi; \
	if [ -n "$$ADMIN_URL" ]; then \
		echo "Testing Admin: $$ADMIN_URL"; \
		HTTP_CODE=$$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$$ADMIN_URL" 2>/dev/null || echo "000"); \
		echo "Admin HTTP Status: $$HTTP_CODE"; \
	fi

# Helper target to manually disable authentication (for debugging)
disable-auth-manual:
	@echo "=== Manually Disabling Authentication ==="
	@echo "This target requires Azure CLI to be logged in manually"
	@FRONTEND_URL=$$(cat frontend_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	ADMIN_URL=$$(cat admin_url.txt 2>/dev/null | tr -d '\n\r' | xargs); \
	export FRONTEND_WEBSITE_URL="$$FRONTEND_URL"; \
	export ADMIN_WEBSITE_URL="$$ADMIN_URL"; \
	if [ -f "disable_auth.sh" ]; then \
		chmod +x disable_auth.sh && ./disable_auth.sh; \
	else \
		echo "ERROR: disable_auth.sh not found"; \
		exit 1; \
	fi

disable-auth-fixed:
	@echo "=== Using Fixed Authentication Disable Script ==="
	@if [ -f "disable_auth_fixed.sh" ]; then \
		chmod +x disable_auth_fixed.sh && ./disable_auth_fixed.sh; \
	else \
		echo "ERROR: disable_auth_fixed.sh not found"; \
		exit 1; \
	fi

destroy: azd-login ## 🧨 Destroy everything in Azure
	@if [ -n "$(AZURE_RESOURCE_GROUP)" ]; then \
		echo "Using resource group: $(AZURE_RESOURCE_GROUP)"; \
		azd down --force --purge --no-prompt --resource-group $(AZURE_RESOURCE_GROUP); \
	else \
		echo "AZURE_RESOURCE_GROUP is not set"; \
		exit 1; \
	fi
