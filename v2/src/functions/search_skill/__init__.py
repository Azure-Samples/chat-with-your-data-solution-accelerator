"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline, task #43)

``search_skill`` blueprint package marker.

Per Hard Rule #13, this ``__init__.py`` carries only the module
docstring (Pillar / Phase header). All blueprint logic lives in
sibling modules: ``models.py`` (U10a -- AI Search custom-skill
request/response Pydantic models), ``handler.py`` (U10b --
embed-on-the-fly handler), ``blueprint.py`` (U10c -- HTTP trigger
entry point, registered in ``functions/function_app.py``).
"""
