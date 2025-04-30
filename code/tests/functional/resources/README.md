# Why is this here?

The file [9b5ad71b2ce5302211f9c61530b329a4922fc6a4](9b5ad71b2ce5302211f9c61530b329a4922fc6a4) is required to stop the 
tiktoken library from making a call out to the internet to retrieve the required encoder.

You can see where this happens in the code here https://github.com/openai/tiktoken/blob/1b9faf2779855124f05174adf1383e53689ed94b/tiktoken/load.py#L25,
which calls out to https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken.

There is an open issue against the library to resolve this problem https://github.com/openai/tiktoken/issues/232.

The stored file is a copy of this remote file.