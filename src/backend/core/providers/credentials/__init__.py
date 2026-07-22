"""Credentials provider domain (package marker only).

Per Hard Rule #13: this `__init__.py` is a
package marker only. The `Registry[type[BaseCredentialProvider]]`
instance, eager concrete-provider side-effect imports, and the
`select_default` domain helper live in `registry.py`. Callers:

    from backend.core.providers.credentials import registry as credentials_registry

    key = credentials_registry.select_default(settings.identity.uami_client_id)
    cred_provider = credentials_registry.registry.get(key)(settings=settings)
"""
