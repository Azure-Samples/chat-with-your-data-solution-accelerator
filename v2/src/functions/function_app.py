"""Azure Functions v2 entry point."""

import azure.functions as func

from .blueprints.add_url_embeddings import bp as add_url_bp
from .blueprints.batch_push_results import bp as batch_push_bp
from .blueprints.batch_start import bp as batch_start_bp
from .blueprints.conversation import bp as conversation_bp
from .blueprints.search_skill import bp as search_skill_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

app.register_functions(add_url_bp)
app.register_functions(batch_start_bp)
app.register_functions(batch_push_bp)
app.register_functions(conversation_bp)
app.register_functions(search_skill_bp)
