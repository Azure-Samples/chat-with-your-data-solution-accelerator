"""``add_url`` blueprint package marker.

Per Hard Rule #13, this ``__init__.py`` carries only the module
docstring. All blueprint logic lives in
sibling modules: ``url_fetcher.py`` (HTTP download primitive),
``handler.py`` (parse / embed / push orchestration), ``blueprint.py``
(HTTP trigger entry point, registered in ``functions/function_app.py``).
"""
