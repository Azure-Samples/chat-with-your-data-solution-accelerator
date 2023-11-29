import json
from .AzureBlobStorageHelper import AzureBlobStorageClient
from ..document_chunking import ChunkingSettings, ChunkingStrategy
from ..document_loading import LoadingSettings, LoadingStrategy
from .DocumentProcessorHelper import Processor
from .OrchestratorHelper import Orchestrator, OrchestrationSettings, OrchestrationStrategy
from .EnvHelper import EnvHelper

CONFIG_CONTAINER_NAME = "config"

class Config:
    def __init__(self, config: dict):
        self.prompts = Prompts(config['prompts'])
        self.messages = Messages(config['messages'])
        self.logging = Logging(config['logging'])
        self.document_processors = [
            Processor(
                document_type=c['document_type'], 
                chunking=ChunkingSettings(c['chunking']), 
                loading=LoadingSettings(c['loading'])
            ) 
            for c in config['document_processors']]
        self.env_helper = EnvHelper()
        self.default_orchestration_settings = {'strategy' : self.env_helper.ORCHESTRATION_STRATEGY}
        self.orchestrator = OrchestrationSettings(config.get('orchestrator', self.default_orchestration_settings))
    
    def get_available_document_types(self):
        return ["txt", "pdf", "url", "html", "md", "jpeg", "jpg", "png", "docx"]    
    
    def get_available_chunking_strategies(self):
        return [c.value for c in ChunkingStrategy]
    
    def get_available_loading_strategies(self):
        return [c.value for c in LoadingStrategy]
    
    def get_available_orchestration_strategies(self):
        return [c.value for c in OrchestrationStrategy]
        
# TODO: Change to AnsweringChain or something, Prompts is not a good name
class Prompts:
    def __init__(self, prompts: dict):
        self.condense_question_prompt = prompts['condense_question_prompt']
        self.answering_prompt = prompts['answering_prompt']
        self.post_answering_prompt = prompts['post_answering_prompt']
        self.enable_post_answering_prompt = prompts['enable_post_answering_prompt']
        self.enable_content_safety = prompts['enable_content_safety']
        
class Messages:
    def __init__(self, messages: dict):
        self.post_answering_filter = messages['post_answering_filter']

class Logging:
    def __init__(self, logging: dict):
        self.log_user_interactions = logging['log_user_interactions']
        self.log_tokens = logging['log_tokens']
        
class ConfigHelper:
    @staticmethod
    def get_active_config_or_default():
        try:
            blob_client = AzureBlobStorageClient(container_name=CONFIG_CONTAINER_NAME)
            config = blob_client.download_file("active.json")
            config = Config(json.loads(config))
        except: 
            print("Returning default config")
            config = ConfigHelper.get_default_config()
        return config 
    
    @staticmethod
    def save_config_as_active(config):
        blob_client = AzureBlobStorageClient(container_name=CONFIG_CONTAINER_NAME)
        blob_client = blob_client.upload_file(json.dumps(config, indent=2), "active.json", content_type='application/json')
        
    @staticmethod
    def get_default_config():
        default_config = {
            "prompts": {
                "condense_question_prompt": """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question. If the user asks multiple questions at once, break them up into multiple standalone questions, all in one line.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:""",
                "answering_prompt": """Context:
{sources}

Please reply to the question using only the information Context section above. If you can't answer a question using the context, reply politely that the information is not in the knowledge base. DO NOT make up your own answers. You detect the language of the question and answer in the same language.  If asked for enumerations list all of them and do not invent any.

The context is structured like this:

[docX]:  <content>
<and more of them>

When you give your answer, you ALWAYS MUST include one or more of the above sources in your response in the following format: <answer> [docX]
Always use square brackets to reference the document source. When you create the answer from multiple sources, list each source separately, e.g. <answer> [docX][docY] and so on.
Always reply in the language of the question.

Question: {question}
Answer:""",
                "post_answering_prompt": """You help fact checking if the given answer for the question below is aligned to the sources. If the answer is correct, then reply with 'True', if the answer is not correct, then reply with 'False'. DO NOT ANSWER with anything else.

Sources:
{sources}

Question: {question}
Answer: {answer}""",
                "enable_post_answering_prompt": False,
                "enable_content_safety": False
                },
            "messages": {
                "post_answering_filter": "I'm sorry, but I can't answer this question correctly. Please try again by altering or rephrasing your question."
            },
            "document_processors": 
                [  
                 {
                    "document_type": "pdf",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.LAYOUT
                    }
                },
                {
                    "document_type": "txt",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.WEB
                    }
                },
                {
                    "document_type": "url",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.WEB
                    }
                },
                {
                    "document_type": "md",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.WEB
                    }
                },
                {
                    "document_type": "html",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.WEB
                    }
                },
                {
                    "document_type": "docx",
                    "chunking": {
                        "strategy": ChunkingStrategy.LAYOUT,
                        "size": 500,
                        "overlap": 100
                    },
                    "loading": {
                        "strategy": LoadingStrategy.DOCX
                    }
                },
            ],
            "logging": {
                "log_user_interactions": True,
                "log_tokens": True
            },
            "orchestrator": {
                "strategy": "openai_function"
            }
        }
        return Config(default_config)