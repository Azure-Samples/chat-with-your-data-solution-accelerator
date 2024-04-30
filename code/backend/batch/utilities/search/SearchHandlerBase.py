from abc import ABC, abstractmethod


class SearchHandlerBase(ABC):
    def __init__(self, env_helper):
        self.env_helper = env_helper
        self.search_client = self.create_search_client()

    @abstractmethod
    def create_search_client(self):
        pass

    @abstractmethod
    def perform_search(self, filename):
        pass

    @abstractmethod
    def process_results(self, results):
        pass

    @abstractmethod
    def get_files(self):
        pass

    @abstractmethod
    def output_results(self, results, id_field):
        pass

    @abstractmethod
    def delete_files(self, files, id_field):
        pass

    @abstractmethod
    def query_search(self, question):
        pass

    @abstractmethod
    def return_answer_source_documents(self, search_results):
        pass
