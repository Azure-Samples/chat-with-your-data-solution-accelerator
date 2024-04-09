from unittest.mock import MagicMock, patch

import pytest
from backend.batch.utilities.common.Answer import Answer
from backend.batch.utilities.tools.QuestionAnswerTool import QuestionAnswerTool
from langchain_core.documents import Document


@pytest.fixture(autouse=True)
def vector_store_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.AzureSearchHelper"
    ) as mock:
        vector_store = mock.return_value.get_vector_store.return_value

        documents = []
        for i in range(4):
            document = Document(f"mock content {i}")
            document.metadata = {
                "id": f"mock id {i}",
                "title": f"mock title {i}",
                "source": f"mock source {i}",
                "chunk": f"mock chunk {i}",
                "offset": f"mock offset {i}",
                "page_number": f"mock page number {i}",
            }
            documents.append(document)

        vector_store.similarity_search.return_value = documents

        yield vector_store


@pytest.fixture(autouse=True)
def config_mock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.ConfigHelper") as mock:
        config = mock.get_active_config_or_default.return_value
        config.prompts.answering_system_prompt = "mock answering system prompt"
        config.prompts.answering_prompt = ""
        config.prompts.include_few_shot_example = True

        yield config


@pytest.fixture(autouse=True)
def env_helper_mock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.EnvHelper") as mock:
        env_helper = mock.return_value
        env_helper.AZURE_OPENAI_SYSTEM_MESSAGE = "mock azure openai system message"

        yield env_helper


@pytest.fixture(autouse=True)
def LLMHelperMock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.LLMHelper") as mock:
        yield mock


@pytest.fixture(autouse=True)
def LLMChainMock():
    with patch("backend.batch.utilities.tools.QuestionAnswerTool.LLMChain") as mock:
        mock.return_value.return_value = {"text": "mock content"}

        yield mock


@pytest.fixture(autouse=True)
def get_openai_callback_mock():
    with patch(
        "backend.batch.utilities.tools.QuestionAnswerTool.get_openai_callback"
    ) as mock:
        yield mock


def test_similarity_search_is_called(vector_store_mock: MagicMock):
    # given
    tool = QuestionAnswerTool()

    # when
    tool.answer_question("mock question", [])

    # then
    vector_store_mock.similarity_search.assert_called_once_with(
        query="mock question", k=4, search_type="hybrid"
    )


def test_answer_question_returns_source_documents():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    source_documents = answer.source_documents

    assert len(source_documents) == 4

    for i, source_document in enumerate(source_documents):
        assert source_document.id == f"mock id {i}"
        assert source_document.title == f"mock title {i}"
        assert source_document.source == f"mock source {i}"
        assert source_document.chunk == f"mock chunk {i}"
        assert source_document.offset == f"mock offset {i}"
        assert source_document.page_number == f"mock page number {i}"


def test_answer_question_returns_answer():
    # given
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    assert isinstance(answer, Answer)
    assert answer.question == "mock question"
    assert answer.answer == "mock content"


def test_get_openai_callback(get_openai_callback_mock: MagicMock):
    # given
    cb = get_openai_callback_mock.return_value.__enter__.return_value
    cb.prompt_tokens = 100
    cb.completion_tokens = 50
    tool = QuestionAnswerTool()

    # when
    answer = tool.answer_question("mock question", [])

    # then
    get_openai_callback_mock.assert_called_once()
    assert answer.prompt_tokens == 100
    assert answer.completion_tokens == 50


def test_correct_prompt_with_few_shot_example(
    LLMHelperMock: MagicMock, LLMChainMock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    llm = LLMHelperMock.return_value.get_llm.return_value
    answer_generator = LLMChainMock.return_value

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "user_question": "mock question",
        "documents": '{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}',
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    assert LLMChainMock.call_args[1]["llm"] == llm
    assert LLMChainMock.call_args[1]["verbose"] is True

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
Human: ## Retrieved Documents
{"retrieved_documents": [{"[doc1]": {"content": "Dual Transformer Encoder (DTE) DTE (https://dev.azure.com/TScience/TSciencePublic/_wiki/wikis/TSciencePublic.wiki/82/Dual-Transformer-Encoder) DTE is a general pair-oriented sentence representation learning framework based on transformers. It provides training, inference and evaluation for sentence similarity models. Model Details DTE can be used to train a model for sentence similarity with the following features: - Build upon existing transformer-based text representations (e.g.TNLR, BERT, RoBERTa, BAG-NLR) - Apply smoothness inducing technology to improve the representation robustness - SMART (https://arxiv.org/abs/1911.03437) SMART - Apply NCE (Noise Contrastive Estimation) based similarity learning to speed up training of 100M pairs We use pretrained DTE model"}}, {"[doc2]": {"content": "trained on internal data. You can find more details here - Models.md (https://dev.azure.com/TScience/_git/TSciencePublic?path=%2FDualTransformerEncoder%2FMODELS.md&version=GBmaster&_a=preview) Models.md DTE-pretrained for In-context Learning Research suggests that finetuned transformers can be used to retrieve semantically similar exemplars for e.g. KATE (https://arxiv.org/pdf/2101.06804.pdf) KATE . They show that finetuned models esp. tuned on related tasks give the maximum boost to GPT-3 in-context performance. DTE have lot of pretrained models that are trained on intent classification tasks. We can use these model embedding to find natural language utterances which are similar to our test utterances at test time. The steps are: 1. Embed"}}, {"[doc3]": {"content": "train and test utterances using DTE model 2. For each test embedding, find K-nearest neighbors. 3. Prefix the prompt with nearest embeddings. The following diagram from the above paper (https://arxiv.org/pdf/2101.06804.pdf) the above paper visualizes this process: DTE-Finetuned This is an extension of DTE-pretrained method where we further finetune the embedding models for prompt crafting task. In summary, we sample random prompts from our training data and use them for GPT-3 inference for the another part of training data. Some prompts work better and lead to right results whereas other prompts lead"}}, {"[doc4]": {"content": "to wrong completions. We finetune the model on the downstream task of whether a prompt is good or not based on whether it leads to right or wrong completion. This approach is similar to this paper: Learning To Retrieve Prompts for In-Context Learning (https://arxiv.org/pdf/2112.08633.pdf) this paper: Learning To Retrieve Prompts for In-Context Learning . This method is very general but it may require a lot of data to actually finetune a model to learn how to retrieve examples suitable for the downstream inference model like GPT-3."}}]}

## User Question
What features does the Dual Transformer Encoder (DTE) provide for sentence similarity models and in-context learning?
AI: The Dual Transformer Encoder (DTE) is a framework for sentence representation learning that can be used to train, infer, and evaluate sentence similarity models[doc1][doc2]. It builds upon existing transformer-based text representations and applies smoothness inducing technology and Noise Contrastive Estimation for improved robustness and faster training[doc1]. DTE also offers pretrained models for in-context learning, which can be used to find semantically similar natural language utterances[doc2]. These models can be further finetuned for specific tasks, such as prompt crafting, to enhance the performance of downstream inference models like GPT-3[doc2][doc3][doc4]. However, this finetuning may require a significant amount of data[doc3][doc4].
System: mock azure openai system message
Human: ## Retrieved Documents
{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}

## User Question
mock question"""
    )


def test_correct_prompt_without_few_shot_example(
    config_mock: MagicMock, LLMChainMock: MagicMock
):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    config_mock.prompts.include_few_shot_example = False

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "user_question": "mock question",
        "documents": '{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}',
        "chat_history": [],
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
System: mock azure openai system message
Human: ## Retrieved Documents
{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}

## User Question
mock question"""
    )


def test_correct_prompt_with_few_shot_example_and_chat_history(LLMChainMock: MagicMock):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
    ]

    # when
    tool.answer_question("mock question", chat_history)

    # then
    expected_input = {
        "user_question": "mock question",
        "documents": '{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}',
        "chat_history": chat_history,
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """System: mock answering system prompt
Human: ## Retrieved Documents
{"retrieved_documents": [{"[doc1]": {"content": "Dual Transformer Encoder (DTE) DTE (https://dev.azure.com/TScience/TSciencePublic/_wiki/wikis/TSciencePublic.wiki/82/Dual-Transformer-Encoder) DTE is a general pair-oriented sentence representation learning framework based on transformers. It provides training, inference and evaluation for sentence similarity models. Model Details DTE can be used to train a model for sentence similarity with the following features: - Build upon existing transformer-based text representations (e.g.TNLR, BERT, RoBERTa, BAG-NLR) - Apply smoothness inducing technology to improve the representation robustness - SMART (https://arxiv.org/abs/1911.03437) SMART - Apply NCE (Noise Contrastive Estimation) based similarity learning to speed up training of 100M pairs We use pretrained DTE model"}}, {"[doc2]": {"content": "trained on internal data. You can find more details here - Models.md (https://dev.azure.com/TScience/_git/TSciencePublic?path=%2FDualTransformerEncoder%2FMODELS.md&version=GBmaster&_a=preview) Models.md DTE-pretrained for In-context Learning Research suggests that finetuned transformers can be used to retrieve semantically similar exemplars for e.g. KATE (https://arxiv.org/pdf/2101.06804.pdf) KATE . They show that finetuned models esp. tuned on related tasks give the maximum boost to GPT-3 in-context performance. DTE have lot of pretrained models that are trained on intent classification tasks. We can use these model embedding to find natural language utterances which are similar to our test utterances at test time. The steps are: 1. Embed"}}, {"[doc3]": {"content": "train and test utterances using DTE model 2. For each test embedding, find K-nearest neighbors. 3. Prefix the prompt with nearest embeddings. The following diagram from the above paper (https://arxiv.org/pdf/2101.06804.pdf) the above paper visualizes this process: DTE-Finetuned This is an extension of DTE-pretrained method where we further finetune the embedding models for prompt crafting task. In summary, we sample random prompts from our training data and use them for GPT-3 inference for the another part of training data. Some prompts work better and lead to right results whereas other prompts lead"}}, {"[doc4]": {"content": "to wrong completions. We finetune the model on the downstream task of whether a prompt is good or not based on whether it leads to right or wrong completion. This approach is similar to this paper: Learning To Retrieve Prompts for In-Context Learning (https://arxiv.org/pdf/2112.08633.pdf) this paper: Learning To Retrieve Prompts for In-Context Learning . This method is very general but it may require a lot of data to actually finetune a model to learn how to retrieve examples suitable for the downstream inference model like GPT-3."}}]}

## User Question
What features does the Dual Transformer Encoder (DTE) provide for sentence similarity models and in-context learning?
AI: The Dual Transformer Encoder (DTE) is a framework for sentence representation learning that can be used to train, infer, and evaluate sentence similarity models[doc1][doc2]. It builds upon existing transformer-based text representations and applies smoothness inducing technology and Noise Contrastive Estimation for improved robustness and faster training[doc1]. DTE also offers pretrained models for in-context learning, which can be used to find semantically similar natural language utterances[doc2]. These models can be further finetuned for specific tasks, such as prompt crafting, to enhance the performance of downstream inference models like GPT-3[doc2][doc3][doc4]. However, this finetuning may require a significant amount of data[doc3][doc4].
System: mock azure openai system message
Human: Hello
AI: Hi, how can I help?
Human: ## Retrieved Documents
{"retrieved_documents": [{"[doc1]": {"content": "mock content 0"}}, {"[doc2]": {"content": "mock content 1"}}, {"[doc3]": {"content": "mock content 2"}}, {"[doc4]": {"content": "mock content 3"}}]}

## User Question
mock question"""
    )


def test_legacy_correct_prompt(config_mock: MagicMock, LLMChainMock: MagicMock):
    # given
    tool = QuestionAnswerTool()
    answer_generator = LLMChainMock.return_value
    config_mock.prompts.answering_prompt = "Sources: {sources}, Question: {question}"

    # when
    tool.answer_question("mock question", [])

    # then
    expected_input = {
        "question": "mock question",
        "sources": "[doc1]: mock content 0\n\n[doc2]: mock content 1\n\n[doc3]: mock content 2\n\n[doc4]: mock content 3",
    }

    answer_generator.assert_called_once_with(expected_input)

    prompt = LLMChainMock.call_args[1]["prompt"]
    prompt_test = prompt.format(**expected_input)

    assert (
        prompt_test
        == """Sources: [doc1]: mock content 0

[doc2]: mock content 1

[doc3]: mock content 2

[doc4]: mock content 3, Question: mock question"""
    )
