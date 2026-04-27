"""Pillar: Stable Core
Phase:  1 (Infrastructure + Project Skeleton, task #19)

Post-provision hook executed by `azd up` / `azd provision` after every
Bicep deployment. Idempotent and safe to re-run.

Responsibilities
----------------
1. If ``AZURE_DB_TYPE == 'postgresql'``: connect to the freshly provisioned
   Flexible Server using the deployer's Entra ID token and run
   ``CREATE EXTENSION IF NOT EXISTS vector`` against the ``postgres``
   database. The server must already have ``vector`` allow-listed via
   the ``azure.extensions`` server parameter (handled in main.bicep).
2. Print a compact summary of the AZURE_* outputs an operator most
   commonly needs (endpoints, deployment names, identity IDs).

Notes
-----
* Table/index DDL for chat history and pgvector indexing belongs to the
  modules that own those schemas (Phase 4, dev_plan tasks #28 and #30).
  Naming-stability rule §11: do not pre-create tables here whose column
  names would lock in a contract before the consuming code exists.
* Authentication uses ``DefaultAzureCredential`` so the script works
  unchanged for an interactive deployer, a service principal in CI, or
  a managed identity in Cloud Shell.
"""

from __future__ import annotations

import os
import sys

REQUIRED_ENV = ("AZURE_DB_TYPE",)
# Mirrors the @allowed() list on `databaseType` in v2/infra/main.bicep.
# Kept in sync by hand: a typo here or there silently breaks deploys.
ALLOWED_DB_TYPES = ("cosmosdb", "postgresql")
POSTGRES_AAD_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
POSTGRES_DB = "postgres"

# Outputs surfaced in the summary block. Kept in display order; missing
# entries are skipped silently (e.g. cosmos vars in postgresql mode).
SUMMARY_KEYS = (
    "AZURE_RESOURCE_GROUP",
    "AZURE_LOCATION",
    "AZURE_AI_SERVICE_LOCATION",
    "AZURE_DB_TYPE",
    "AZURE_INDEX_STORE",
    "AZURE_AI_SERVICES_ENDPOINT",
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_OPENAI_GPT_DEPLOYMENT",
    "AZURE_OPENAI_REASONING_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "AZURE_AI_SEARCH_ENDPOINT",
    "AZURE_COSMOS_ENDPOINT",
    "AZURE_POSTGRES_HOST",
    "AZURE_POSTGRES_NAME",
    "AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME",
    "AZURE_STORAGE_ACCOUNT_NAME",
    "AZURE_BACKEND_URL",
    "AZURE_FRONTEND_URL",
    "AZURE_FUNCTION_APP_URL",
    "AZURE_APP_INSIGHTS_CONNECTION_STRING",
)


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.stderr.write(
            f"post-provision: required environment variable {name} is not set. "
            "Run via `azd hooks run postprovision` or `azd provision`.\n"
        )
        sys.exit(2)
    return value


def _enable_pgvector() -> None:
    host = _require("AZURE_POSTGRES_HOST")
    admin_user = _require("AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME")

    # Private-networking pre-flight: if the server FQDN is in the
    # `*.private.postgres.database.azure.com` zone the deployer machine
    # cannot resolve it from outside the VNet. Fail loudly with an
    # actionable Bastion-tunnel command instead of letting psycopg2
    # raise an opaque `could not translate host name` error.
    if ".private.postgres.database.azure.com" in host:
        bastion = os.environ.get("AZURE_BASTION_NAME", "<bastion-name>")
        rg = os.environ.get("AZURE_RESOURCE_GROUP", "<resource-group>")
        pg_name = os.environ.get("AZURE_POSTGRES_NAME", "<postgres-name>")
        sys.stderr.write(
            "post-provision: postgres is in private mode and unreachable "
            f"from this machine ({host}).\n"
            "  fix: open a Bastion tunnel in another terminal, then re-run "
            "`azd hooks run postprovision`:\n\n"
            f"    az network bastion tunnel \\\n      --resource-group {rg} \\\n      --name {bastion} \\\n      --target-resource-id $(az postgres flexible-server show "
            f"-g {rg} -n {pg_name} --query id -o tsv) \\\n      --resource-port 5432 --port 5432\n\n"
            "  then set AZURE_POSTGRES_HOST=localhost and re-run.\n"
        )
        sys.exit(7)

    # Imports are deferred so the script's summary block still runs in
    # cosmosdb mode without these packages installed.
    try:
        import psycopg2  # type: ignore[import-not-found]
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover - environment guard
        sys.stderr.write(
            "post-provision: missing dependency for postgres setup "
            f"({exc.name}). Run `uv sync` from the repo root first.\n"
        )
        sys.exit(3)

    print(f"post-provision: acquiring Entra token for {host}")
    try:
        token = DefaultAzureCredential().get_token(POSTGRES_AAD_SCOPE).token
    except Exception as exc:  # noqa: BLE001 - surface auth failures verbatim
        sys.stderr.write(
            "post-provision: failed to acquire an Entra token for "
            f"{POSTGRES_AAD_SCOPE}.\n  cause: {exc}\n  fix: run `az login` "
            "as the deployer principal, or set AZURE_CLIENT_ID/"
            "AZURE_CLIENT_SECRET/AZURE_TENANT_ID for a service principal.\n"
        )
        sys.exit(4)

    print(f"post-provision: connecting as {admin_user}@{host}/{POSTGRES_DB}")
    try:
        conn = psycopg2.connect(
            host=host,
            user=admin_user,
            dbname=POSTGRES_DB,
            password=token,
            sslmode="require",
        )
    except Exception as exc:  # noqa: BLE001 - surface connect failures verbatim
        sys.stderr.write(
            f"post-provision: failed to connect to {admin_user}@{host}/"
            f"{POSTGRES_DB}.\n  cause: {exc}\n  likely causes:\n"
            "    * AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME does not match the "
            "AAD admin configured on the server\n"
            "    * client IP not allowed by the server firewall (public mode) "
            "or private DNS not resolving (private mode)\n"
            "    * the deployer's token does not have the "
            "`https://ossrdbms-aad.database.windows.net/.default` scope\n"
        )
        sys.exit(5)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    finally:
        conn.close()
    print("post-provision: pgvector extension ready")


def _print_summary() -> None:
    print("\n=== azd outputs ===")
    width = max(len(k) for k in SUMMARY_KEYS)
    for key in SUMMARY_KEYS:
        value = os.environ.get(key, "")
        if value:
            print(f"  {key.ljust(width)}  {value}")
    print("===================\n")


def main() -> int:
    for var in REQUIRED_ENV:
        _require(var)

    db_type = os.environ["AZURE_DB_TYPE"].strip().lower()
    if db_type not in ALLOWED_DB_TYPES:
        sys.stderr.write(
            f"post-provision: AZURE_DB_TYPE={db_type!r} is not one of "
            f"{ALLOWED_DB_TYPES}. Check the `databaseType` parameter in "
            "v2/infra/main.parameters.json (or the AZURE_ENV_DB_TYPE "
            "value set via `azd env set`).\n"
        )
        return 6

    if db_type == "postgresql":
        _enable_pgvector()
    else:
        print(f"post-provision: AZURE_DB_TYPE={db_type!r}; skipping postgres setup")

    _print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
