import azure.functions as func
from AddURLEmbeddings import bp_add_url_embeddings
from BatchPushResults import bp_batch_push_results
from BatchStartProcessing import bp_batch_start_processing
from GetConversationResponse import bp_get_conversation_response

app = func.FunctionApp(
    http_auth_level=func.AuthLevel.FUNCTION
)  # change to ANONYMOUS for local debugging
app.register_functions(bp_add_url_embeddings)
app.register_functions(bp_batch_push_results)
app.register_functions(bp_batch_start_processing)
app.register_functions(bp_get_conversation_response)
