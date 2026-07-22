"""Live-container smoke tests. Excluded from the default pytest run by
``addopts = "-m 'not smoke'"``. Executed by the GitHub Actions
``backend-only smoke`` workflow after
``docker compose ... --profile backend-only up``.
"""
