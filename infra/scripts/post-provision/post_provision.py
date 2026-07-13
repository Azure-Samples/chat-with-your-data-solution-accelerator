"""Pillar: Stable Core
Phase:  1 (Infrastructure + Project Skeleton, task #19)
Phase:  3 (Conversation + RAG, task #26 — search-index bootstrap)
Phase:  8 (agent_framework default + Foundry IQ Knowledge Base — KB seed)

Post-provision hook executed by `azd up` / `azd provision` after every
Bicep deployment. Idempotent and safe to re-run.

Responsibilities
----------------
1. If ``AZURE_DB_TYPE == 'postgresql'``: connect to the freshly provisioned
   Flexible Server using the deployer's Entra ID token and run
   ``CREATE EXTENSION IF NOT EXISTS vector`` against the ``postgres``
   database. The server must already have ``vector`` allow-listed via
   the ``azure.extensions`` server parameter (handled in main.bicep).
2. If ``AZURE_AI_SEARCH_ENDPOINT`` is set (cosmosdb mode): ensure the
   chat index exists with the schema the ``azure_search`` provider
   reads. Idempotent (no-op when the index already exists).
3. Print a compact summary of the AZURE_* outputs an operator most
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
* ``--dry-run`` skips every external SDK call (no postgres connect, no
  Search index create) but still validates env vars and prints the
  summary. Wire-trace before a real deploy.
"""

import argparse
import os
import sys
from typing import Sequence

import httpx
import psycopg2  # type: ignore[import-not-found]
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

REQUIRED_ENV = ("AZURE_DB_TYPE",)
# Mirrors the @allowed() list on `databaseType` in v2/infra/main.bicep.
# Kept in sync by hand: a typo here or there silently breaks deploys.
ALLOWED_DB_TYPES = ("cosmosdb", "postgresql")
POSTGRES_AAD_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
POSTGRES_DB = "postgres"

# Chat search index schema. Field names match those the
# `azure_search` provider reads in v2/src/providers/search/azure_search.py
# (id / content / title / url / content_vector). Re-naming here without
# the corresponding provider change breaks Phase 3 RAG retrieval.
DEFAULT_INDEX_NAME = "cwyd-index"
DEFAULT_EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small / -ada-002
VECTOR_PROFILE_NAME = "cwyd-vector-profile"
HNSW_ALGORITHM_NAME = "cwyd-hnsw"
SEMANTIC_CONFIG_NAME = "default"

# Foundry IQ Knowledge Base seed. A `searchIndex` knowledge source wraps
# the existing chat index, and the knowledge base references that source
# plus the Azure OpenAI reasoning model used for query planning. Created
# once via the Search REST `knowledgesources` / `knowledgebases` endpoints
# (api-version from SearchSettings) — never per-document. The two `kind`
# discriminators below are the only values this script emits, so they are
# pinned as single-value constants.
KNOWLEDGE_SOURCE_KIND_SEARCH_INDEX = "searchIndex"
KNOWLEDGE_BASE_MODEL_KIND_AZURE_OPENAI = "azureOpenAI"
# Index fields surfaced as citation "referenced source data" so Foundry IQ
# knowledge-base citations carry the friendly filename (`title`), document
# `url`, and chunk `content` snippet rather than only the raw document key.
# These mirror the index schema in `_ensure_search_index` (title / url /
# content) and the `title` / `content` semantic fields; the KB REST contract
# takes `searchIndexParameters.sourceDataFields` as `{"name": <field>}` refs.
KNOWLEDGE_SOURCE_SOURCE_DATA_FIELDS = ("title", "url", "content")
# Defaults mirror SearchSettings. The script reads env directly rather than
# importing settings, matching `_ensure_search_index`'s DEFAULT_INDEX_NAME.
DEFAULT_KNOWLEDGE_BASE_NAME = "cwyd-kb"
DEFAULT_KNOWLEDGE_SOURCE_NAME = "cwyd-index-ks"
DEFAULT_KNOWLEDGE_BASE_API_VERSION = "2025-11-01-preview"
# OAuth scope for the Azure AI Search data plane (knowledgesources /
# knowledgebases REST PUT). Distinct from the postgres AAD scope above.
SEARCH_DATA_PLANE_SCOPE = "https://search.azure.com/.default"

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


def _resolve_deployer_upn() -> str:
    """Resolve the deployer's Postgres username.

    Priority: AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME (Bicep output, exact
    value registered as admin) > az CLI > AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME.
    """
    import subprocess

    # Bicep output: the exact principalName used when registering the
    # deployer as a Postgres Entra admin (deployer().userPrincipalName).
    deployer_name = os.environ.get("AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME", "").strip()
    if deployer_name:
        return deployer_name

    try:
        result = subprocess.run(
            [
                "az",
                "ad",
                "signed-in-user",
                "show",
                "--query",
                "userPrincipalName",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            shell=True,
        )
        upn = result.stdout.strip()
        if upn:
            return upn
    except Exception:
        pass
    # Last resort fallback
    value = os.environ.get("AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME", "").strip()
    if value:
        return value
    sys.stderr.write(
        "post-provision: could not resolve deployer UPN. "
        "Run `az login` or set PRINCIPAL_NAME.\n"
    )
    sys.exit(2)


def _enable_pgvector() -> None:
    host = _require("AZURE_POSTGRES_HOST")
    admin_user = _resolve_deployer_upn()

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


def _build_chat_index(name: str, dimensions: int):
    """Build the SearchIndex object the chat path retrieves against."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(name="url", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=HNSW_ALGORITHM_NAME)],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=HNSW_ALGORITHM_NAME,
            )
        ],
    )
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG_NAME,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            )
        ]
    )
    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


def _ensure_search_index(*, dry_run: bool, client_factory=None) -> str:
    """Create the chat index when missing; no-op when it exists.

    Returns one of: ``"skipped"`` (no endpoint configured),
    ``"dry-run"``, ``"exists"``, ``"created"``. ``client_factory`` is
    a test seam — production passes ``None`` and the function builds a
    ``SearchIndexClient`` from the deployer's ``DefaultAzureCredential``.
    """
    endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        print("post-provision: AZURE_AI_SEARCH_ENDPOINT not set; skipping search index")
        return "skipped"

    index_name = (
        os.environ.get("AZURE_AI_SEARCH_INDEX", "").strip() or DEFAULT_INDEX_NAME
    )
    dimensions_raw = os.environ.get("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "").strip()
    try:
        dimensions = (
            int(dimensions_raw) if dimensions_raw else DEFAULT_EMBEDDING_DIMENSIONS
        )
    except ValueError:
        sys.stderr.write(
            f"post-provision: AZURE_OPENAI_EMBEDDING_DIMENSIONS={dimensions_raw!r} "
            "is not a valid integer.\n"
        )
        sys.exit(8)

    if dry_run:
        print(
            f"post-provision: [dry-run] would ensure index {index_name!r} on {endpoint} "
            f"with vector dimensions={dimensions}"
        )
        return "dry-run"

    if client_factory is None:

        def client_factory():  # type: ignore[no-redef]
            return SearchIndexClient(
                endpoint=endpoint, credential=DefaultAzureCredential()
            )

    client = client_factory()
    try:
        # `get_index` raises ResourceNotFoundError when missing; any other
        # exception (auth, network, malformed endpoint) propagates.
        try:
            client.get_index(index_name)
            print(f"post-provision: search index {index_name!r} already exists")
            return "exists"
        except Exception as exc:  # noqa: BLE001 - normalized below
            if exc.__class__.__name__ != "ResourceNotFoundError":
                raise
            index = _build_chat_index(index_name, dimensions)
            client.create_index(index)
            print(
                f"post-provision: created search index {index_name!r} "
                f"(vector dimensions={dimensions})"
            )
            return "created"
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _build_knowledge_base_seed(
    *,
    knowledge_source_name: str,
    knowledge_base_name: str,
    index_name: str,
    semantic_configuration_name: str,
    openai_resource_uri: str,
    query_planning_deployment: str,
    query_planning_model_name: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build the ``(knowledge_source, knowledge_base)`` REST request bodies.

    Returns the two PUT bodies the Foundry IQ KB seed needs, in order:

    1. A ``searchIndex`` knowledge source that wraps ``index_name`` (the
       existing chat index) and pins ``semantic_configuration_name`` so
       agentic retrieval uses the index's semantic configuration. It also
       requests ``title`` / ``url`` / ``content`` as citation
       ``sourceDataFields`` so knowledge-base citations carry the friendly
       filename and a content snippet, not only the raw document key.
    2. A knowledge base that references the knowledge source by name and
       lists the Azure OpenAI chat model used for query planning. The
       Foundry IQ knowledge base API only accepts chat models here (for
       example gpt-4o-mini, gpt-4.1, gpt-5.1); o-series reasoning models
       are rejected, so this is the chat deployment, not the reasoning one.

    The shapes match the Azure AI Search ``knowledgesources`` /
    ``knowledgebases`` REST contract; the caller pins the api-version from
    ``SearchSettings.knowledge_base_api_version`` and PUTs each body. These
    are externally-owned REST payloads, so plain dicts rather than typed
    models.
    """
    knowledge_source_body: dict[str, object] = {
        "name": knowledge_source_name,
        "kind": KNOWLEDGE_SOURCE_KIND_SEARCH_INDEX,
        "searchIndexParameters": {
            "searchIndexName": index_name,
            "semanticConfigurationName": semantic_configuration_name,
            "sourceDataFields": [
                {"name": field} for field in KNOWLEDGE_SOURCE_SOURCE_DATA_FIELDS
            ],
        },
    }
    knowledge_base_body: dict[str, object] = {
        "name": knowledge_base_name,
        "knowledgeSources": [{"name": knowledge_source_name}],
        "models": [
            {
                "kind": KNOWLEDGE_BASE_MODEL_KIND_AZURE_OPENAI,
                "azureOpenAIParameters": {
                    "resourceUri": openai_resource_uri,
                    "deploymentId": query_planning_deployment,
                    "modelName": query_planning_model_name,
                },
            }
        ],
    }
    return knowledge_source_body, knowledge_base_body


def _ensure_knowledge_base(*, dry_run: bool, client_factory=None) -> str:
    """Create-or-update the Foundry IQ knowledge source + knowledge base.

    Grounds the agent_framework orchestrator: a ``searchIndex`` knowledge
    source wraps the chat index, and the knowledge base references that
    source plus the Azure OpenAI chat model used for query planning (Foundry
    IQ rejects o-series reasoning models for the knowledge base model).

    Idempotent: the Search REST ``knowledgesources`` / ``knowledgebases``
    PUT endpoints are create-or-update, so re-running overwrites the seed
    in place (no per-document work). Returns one of: ``"skipped"`` (no
    search endpoint -- postgresql mode), ``"dry-run"``, ``"ensured"``.

    The api-version is read from ``AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION``
    (``SearchSettings.knowledge_base_api_version``) so an operator can bump
    it via env var without a code change. ``client_factory`` is a test seam
    -- production passes ``None`` and the function builds an ``httpx.Client``
    bearer-authed for the Search data plane.
    """
    endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        print(
            "post-provision: AZURE_AI_SEARCH_ENDPOINT not set; "
            "skipping knowledge base"
        )
        return "skipped"

    index_name = (
        os.environ.get("AZURE_AI_SEARCH_INDEX", "").strip() or DEFAULT_INDEX_NAME
    )
    knowledge_source_name = (
        os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME", "").strip()
        or DEFAULT_KNOWLEDGE_SOURCE_NAME
    )
    knowledge_base_name = (
        os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME", "").strip()
        or DEFAULT_KNOWLEDGE_BASE_NAME
    )
    api_version = (
        os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION", "").strip()
        or DEFAULT_KNOWLEDGE_BASE_API_VERSION
    )

    # The KB query-planning model lives on the Azure OpenAI account. Foundry
    # IQ knowledge bases only accept a chat model here (gpt-4o-mini, gpt-4.1,
    # gpt-5.1, ...); o-series reasoning models are rejected with a 400, so the
    # KB uses the chat deployment (AZURE_OPENAI_GPT_DEPLOYMENT), not the
    # reasoning one. In this repo the deployment is named after its model
    # (Bicep wires the deployment and the model from the same `gptModelName`
    # param), so the deployment id doubles as the model name unless an operator
    # overrides it via AZURE_OPENAI_GPT_MODEL_NAME.
    openai_resource_uri = (
        os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        or os.environ.get("AZURE_AI_SERVICES_ENDPOINT", "").strip()
    )
    query_planning_deployment = os.environ.get(
        "AZURE_OPENAI_GPT_DEPLOYMENT", ""
    ).strip()
    query_planning_model_name = (
        os.environ.get("AZURE_OPENAI_GPT_MODEL_NAME", "").strip()
        or query_planning_deployment
    )
    if not openai_resource_uri or not query_planning_deployment:
        sys.stderr.write(
            "post-provision: knowledge base seed needs AZURE_OPENAI_ENDPOINT "
            "(or AZURE_AI_SERVICES_ENDPOINT) and "
            "AZURE_OPENAI_GPT_DEPLOYMENT.\n"
        )
        sys.exit(9)

    if dry_run:
        print(
            f"post-provision: [dry-run] would ensure knowledge base "
            f"{knowledge_base_name!r} (source {knowledge_source_name!r} over "
            f"index {index_name!r}) on {endpoint} using api-version {api_version}"
        )
        return "dry-run"

    knowledge_source_body, knowledge_base_body = _build_knowledge_base_seed(
        knowledge_source_name=knowledge_source_name,
        knowledge_base_name=knowledge_base_name,
        index_name=index_name,
        semantic_configuration_name=SEMANTIC_CONFIG_NAME,
        openai_resource_uri=openai_resource_uri,
        query_planning_deployment=query_planning_deployment,
        query_planning_model_name=query_planning_model_name,
    )

    if client_factory is None:

        def client_factory():  # type: ignore[no-redef]
            token = DefaultAzureCredential().get_token(SEARCH_DATA_PLANE_SCOPE).token
            return httpx.Client(
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

    base = endpoint.rstrip("/")
    params = {"api-version": api_version}
    client = client_factory()
    try:
        # Order matters: the knowledge base references the source by name,
        # so the source PUT must land first. Both PUTs are create-or-update.
        for url, body in (
            (
                f"{base}/knowledgesources('{knowledge_source_name}')",
                knowledge_source_body,
            ),
            (f"{base}/knowledgebases('{knowledge_base_name}')", knowledge_base_body),
        ):
            response = client.put(url, params=params, json=body)
            response.raise_for_status()
        print(
            f"post-provision: knowledge base {knowledge_base_name!r} ready "
            f"(source {knowledge_source_name!r} over index {index_name!r})"
        )
        return "ensured"
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="post-provision",
        description="azd post-provision hook (idempotent).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate env + print summary without making any SDK calls.",
    )
    args = parser.parse_args(argv)

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
        if args.dry_run:
            print("post-provision: [dry-run] would enable pgvector extension")
        else:
            _enable_pgvector()
    else:
        print(f"post-provision: AZURE_DB_TYPE={db_type!r}; skipping postgres setup")

    # AI Search index + Foundry IQ knowledge base are only relevant in
    # cosmosdb mode (PostgreSQL mode uses pgvector for vector indexing).
    if db_type != "postgresql":
        _ensure_search_index(dry_run=args.dry_run)
        _ensure_knowledge_base(dry_run=args.dry_run)
    else:
        print("post-provision: PostgreSQL mode; skipping search index & knowledge base")

    # _print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
