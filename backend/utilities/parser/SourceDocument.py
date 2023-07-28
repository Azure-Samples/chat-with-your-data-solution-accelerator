
class SourceDocument:
    
    def __init__(self, id: str, content: str, title: str, source_url: str, chunk: int, offset: int):
        self.id = id
        self.content = content
        self.title = title
        self.source_url = source_url
        self.chunk = chunk
        self.offset = offset