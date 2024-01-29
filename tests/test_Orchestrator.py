import pytest
from code.utilities.helpers.OrchestratorHelper import Orchestrator, OrchestrationSettings

@pytest.mark.azure("This test requires Azure Open AI configured")
def test_orchestrator_openai_function():
    message_orchestrator = Orchestrator()
    strategy = "openai_function"
    messages = message_orchestrator.handle_message(user_message="What's Azure AI Search?", chat_history=[], conversation_id="test_openai_function", orchestrator = OrchestrationSettings({"strategy" : strategy}))    
    assert messages[-1]['role'] == 'assistant'
    assert messages[-1]['content'] != ''
    
@pytest.mark.azure("This test requires Azure Open AI configured")
def test_orchestrator_langchain():
    message_orchestrator = Orchestrator()
    strategy = "langchain"
    messages = message_orchestrator.handle_message(user_message="What's Azure AI Search?", chat_history=[], conversation_id="test_langchain", orchestrator = OrchestrationSettings({"strategy" : strategy}))    
    assert messages[-1]['role'] == 'assistant'
    assert messages[-1]['content'] != ''
    