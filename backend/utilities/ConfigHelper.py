import os
import json
from enum import Enum
from .azureblobstorage import AzureBlobStorageClient

CONFIG_CONTAINER_NAME = "config"

class ChunkingStrategy(Enum):
    LAYOUT = 'layout'
    PAGE = 'page'
    FIXED_SIZE_OVERLAP = 'fixed_size_overlap'
    SENTENCE = 'sentence'

class Config:
    def __init__(self, config):
        self.prompts = Prompts(config['prompts'])
        self.chunking = [Chunking(x) for x in config['chunking']]
        self.logging = Logging(config['logging'])

class Prompts:
    def __init__(self, prompts):
        self.condense_question_prompt = prompts['condense_question_prompt']
        self.answering_prompt = prompts['answering_prompt']
        self.post_answering_prompt = prompts['post_answering_prompt']

class Chunking:
    def __init__(self, chunking):
        self.chunking_strategy = ChunkingStrategy(chunking['strategy'])
        self.chunk_size = chunking['size']
        self.chunk_overlap = chunking['overlap']

class Logging:
    def __init__(self, logging):
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
                "condense_question_prompt": """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:""",
                "answering_prompt": """{summaries}

Please reply to the question using only the information present in the text above.
If you can't find it, reply politely that the information is not in the knowledge base.
Detect the language of the question and answer in the same language. 
If asked for enumerations list all of them and do not invent any.

Each source has a name followed by a colon and the actual information, always include the source name for each fact you use in the response. Always use double square brackets to reference the filename source, e.g. [[info1.pdf.txt]]. Don't combine sources, list each source separately, e.g. [[info1.pdf]][[info2.txt]].

Question: {question}
Answer:""",
                "post_answering_prompt": "",
                },
            "chunking": [{
                "strategy": ChunkingStrategy.FIXED_SIZE_OVERLAP,
                "size": 500,
                "overlap": 100
                }],
            "logging": {
                "log_user_interactions": True,
                "log_tokens": True
            }
        }
        return Config(default_config)