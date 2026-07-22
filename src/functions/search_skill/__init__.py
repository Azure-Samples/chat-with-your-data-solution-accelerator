"""``search_skill`` blueprint package marker.

Per Hard Rule #13, this ``__init__.py`` carries only the module
docstring. All blueprint logic lives in
sibling modules: ``models.py`` (AI Search custom-skill
request/response Pydantic models), ``handler.py`` (embed-on-the-fly
handler), ``blueprint.py`` (HTTP trigger entry point, registered in
``functions/function_app.py``).
"""
