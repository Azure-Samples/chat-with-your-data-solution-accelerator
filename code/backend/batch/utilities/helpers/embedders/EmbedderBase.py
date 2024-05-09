from abc import ABC, abstractmethod


class EmbedderBase(ABC):
    @abstractmethod
    def embed_file(self, source_url: str, file_name: str):
        pass
