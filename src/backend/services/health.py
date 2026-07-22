"""Health-probe diagnostic helpers shared by the health router."""

from backend.core.settings import AppSettings, DbType, IndexStore
from backend.models.health import (
    CheckStatus,
    DependencyCheck,
    HealthResponse,
    OverallStatus,
)

__all__ = ["run_health_checks"]


def _check_foundry(settings: AppSettings) -> DependencyCheck:
    if not settings.foundry.project_endpoint:
        return DependencyCheck(
            name="foundry_iq",
            status=CheckStatus.FAIL,
            detail="AZURE_AI_PROJECT_ENDPOINT is not set.",
        )
    if not settings.openai.gpt_deployment:
        return DependencyCheck(
            name="foundry_iq",
            status=CheckStatus.FAIL,
            detail="AZURE_OPENAI_GPT_DEPLOYMENT is not set.",
        )
    return DependencyCheck(name="foundry_iq", status=CheckStatus.PASS)


def _check_database(settings: AppSettings) -> DependencyCheck:
    db = settings.database
    # Diagnostic display only -- picks which configured endpoint string to surface in the health payload.
    # Not provider dispatch (no class instantiation, no behavior branch); database provider selection
    # goes through `databases_registry.registry.get(db.db_type)` per Hard Rule #4.
    endpoint = (
        db.cosmos_endpoint if db.db_type == DbType.COSMOSDB else db.postgres_endpoint
    )
    if not endpoint:
        return DependencyCheck(
            name="database",
            status=CheckStatus.FAIL,
            detail=f"No endpoint configured for db_type={db.db_type!r}.",
        )
    return DependencyCheck(
        name="database", status=CheckStatus.PASS, detail=f"db_type={db.db_type}"
    )


def _check_search(settings: AppSettings) -> DependencyCheck:
    # Diagnostic display only -- picks which configured search check to report.
    # Not provider dispatch; search provider selection goes through `search.create(db.index_store, ...)` per Hard Rule #4.
    if settings.database.index_store == IndexStore.AZURE_SEARCH:
        if not settings.search.endpoint:
            return DependencyCheck(
                name="search",
                status=CheckStatus.FAIL,
                detail="AZURE_AI_SEARCH_ENDPOINT is not set.",
            )
        return DependencyCheck(
            name="search", status=CheckStatus.PASS, detail="AzureSearch"
        )
    return DependencyCheck(
        name="search",
        status=CheckStatus.SKIP,
        detail=f"index_store={settings.database.index_store} (no separate search service)",
    )


def _aggregate(checks: list[DependencyCheck]) -> OverallStatus:
    """Aggregate per-check status into an overall status.

    `skip` is neutral -- a check that doesn't apply to this deployment mode
    (e.g. Azure Search in pgvector mode) must not drag the overall status down.
    Reserve `degraded` for future optional-check failures.
    """
    if any(c.status is CheckStatus.FAIL for c in checks):
        return OverallStatus.FAIL
    return OverallStatus.PASS


def run_health_checks(settings: AppSettings) -> HealthResponse:
    """Run every dependency probe and assemble the aggregated response."""
    checks = [
        _check_foundry(settings),
        _check_database(settings),
        _check_search(settings),
    ]
    return HealthResponse(
        status=_aggregate(checks),
        checks=checks,
    )
