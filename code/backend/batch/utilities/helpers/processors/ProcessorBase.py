from abc import ABC, abstractmethod


class ProcessorBase(ABC):
    @abstractmethod
    def process_file(self, source_url: str, file_name: str):
        pass
