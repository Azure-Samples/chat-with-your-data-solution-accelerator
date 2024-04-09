import json
import logging
from .AnsweringToolBase import AnsweringToolBase

from langchain.chains.llm import LLMChain
from langchain.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)
from langchain_community.callbacks import get_openai_callback
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage

from ..helpers.AzureSearchHelper import AzureSearchHelper
from ..helpers.ConfigHelper import ConfigHelper
from ..helpers.EnvHelper import EnvHelper
from ..helpers.LLMHelper import LLMHelper
from ..common.Answer import Answer
from ..common.SourceDocument import SourceDocument

logger = logging.getLogger(__name__)


class QuestionAnswerTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "QuestionAnswer"
        self.vector_store = AzureSearchHelper().get_vector_store()
        self.verbose = True
        self.env_helper = EnvHelper()
        self.config = ConfigHelper.get_active_config_or_default()

        self._user_prompt = """## Retrieved Documents
{documents}

## User Question
{user_question}"""

        self._few_shot_example = {
            "documents": json.dumps(
                {
                    "retrieved_documents": [
                        {
                            "[doc1]": {
                                "content": "Dual Transformer Encoder (DTE) DTE (https://dev.azure.com/TScience/TSciencePublic/_wiki/wikis/TSciencePublic.wiki/82/Dual-Transformer-Encoder) DTE is a general pair-oriented sentence representation learning framework based on transformers. It provides training, inference and evaluation for sentence similarity models. Model Details DTE can be used to train a model for sentence similarity with the following features: - Build upon existing transformer-based text representations (e.g.TNLR, BERT, RoBERTa, BAG-NLR) - Apply smoothness inducing technology to improve the representation robustness - SMART (https://arxiv.org/abs/1911.03437) SMART - Apply NCE (Noise Contrastive Estimation) based similarity learning to speed up training of 100M pairs We use pretrained DTE model"
                            }
                        },
                        {
                            "[doc2]": {
                                "content": "trained on internal data. You can find more details here - Models.md (https://dev.azure.com/TScience/_git/TSciencePublic?path=%2FDualTransformerEncoder%2FMODELS.md&version=GBmaster&_a=preview) Models.md DTE-pretrained for In-context Learning Research suggests that finetuned transformers can be used to retrieve semantically similar exemplars for e.g. KATE (https://arxiv.org/pdf/2101.06804.pdf) KATE . They show that finetuned models esp. tuned on related tasks give the maximum boost to GPT-3 in-context performance. DTE have lot of pretrained models that are trained on intent classification tasks. We can use these model embedding to find natural language utterances which are similar to our test utterances at test time. The steps are: 1. Embed"
                            }
                        },
                        {
                            "[doc3]": {
                                "content": "train and test utterances using DTE model 2. For each test embedding, find K-nearest neighbors. 3. Prefix the prompt with nearest embeddings. The following diagram from the above paper (https://arxiv.org/pdf/2101.06804.pdf) the above paper visualizes this process: DTE-Finetuned This is an extension of DTE-pretrained method where we further finetune the embedding models for prompt crafting task. In summary, we sample random prompts from our training data and use them for GPT-3 inference for the another part of training data. Some prompts work better and lead to right results whereas other prompts lead"
                            }
                        },
                        {
                            "[doc4]": {
                                "content": "to wrong completions. We finetune the model on the downstream task of whether a prompt is good or not based on whether it leads to right or wrong completion. This approach is similar to this paper: Learning To Retrieve Prompts for In-Context Learning (https://arxiv.org/pdf/2112.08633.pdf) this paper: Learning To Retrieve Prompts for In-Context Learning . This method is very general but it may require a lot of data to actually finetune a model to learn how to retrieve examples suitable for the downstream inference model like GPT-3."
                            }
                        },
                    ]
                }
            ),
            "user_question": "What features does the Dual Transformer Encoder (DTE) provide for sentence similarity models and in-context learning?",
            "answer": "The Dual Transformer Encoder (DTE) is a framework for sentence representation learning that can be used to train, infer, and evaluate sentence similarity models[doc1][doc2]. It builds upon existing transformer-based text representations and applies smoothness inducing technology and Noise Contrastive Estimation for improved robustness and faster training[doc1]. DTE also offers pretrained models for in-context learning, which can be used to find semantically similar natural language utterances[doc2]. These models can be further finetuned for specific tasks, such as prompt crafting, to enhance the performance of downstream inference models like GPT-3[doc2][doc3][doc4]. However, this finetuning may require a significant amount of data[doc3][doc4].",
        }

    def legacy_generate_llm_chain(self, question: str, sources: list[Document]):
        answering_prompt = PromptTemplate(
            template=self.config.prompts.answering_prompt,
            input_variables=["question", "sources"],
        )

        # Generate answer from sources
        sources_text = "\n\n".join(
            [f"[doc{i+1}]: {source.page_content}" for i, source in enumerate(sources)]
        )

        return answering_prompt, {
            "question": question,
            "sources": sources_text,
        }

    def generate_llm_chain(
        self,
        question: str,
        chat_history: list[dict],
        sources: list[Document],
    ):
        examples = (
            [self._few_shot_example]
            if self.config.prompts.include_few_shot_example
            else []
        )

        example_prompt = ChatPromptTemplate.from_messages(
            [
                HumanMessagePromptTemplate.from_template(self._user_prompt),
                AIMessagePromptTemplate.from_template("{answer}"),
            ]
        )

        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
        )

        answering_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.config.prompts.answering_system_prompt),
                few_shot_prompt,
                SystemMessage(content=self.env_helper.AZURE_OPENAI_SYSTEM_MESSAGE),
                MessagesPlaceholder("chat_history"),
                HumanMessagePromptTemplate.from_template(self._user_prompt),
            ]
        )

        # Generate answer from sources
        documents = json.dumps(
            {
                "retrieved_documents": [
                    {f"[doc{i+1}]": {"content": source.page_content}}
                    for i, source in enumerate(sources)
                ],
            }
        )

        return answering_prompt, {
            "user_question": question,
            "documents": documents,
            "chat_history": chat_history,
        }

    def answer_question(self, question: str, chat_history: list[dict], **kwargs: dict):
        # Retrieve documents as sources
        sources = self.vector_store.similarity_search(
            query=question, k=4, search_type="hybrid"
        )

        # If answering_prompt has been set, then use legacy_generate_llm_chain for backwards compatibility
        if self.config.prompts.answering_prompt:
            answering_prompt, input = self.legacy_generate_llm_chain(question, sources)
        else:
            answering_prompt, input = self.generate_llm_chain(
                question, chat_history, sources
            )

        llm_helper = LLMHelper()

        answer_generator = LLMChain(
            llm=llm_helper.get_llm(), prompt=answering_prompt, verbose=self.verbose
        )

        with get_openai_callback() as cb:
            result = answer_generator(input)

        answer = result["text"]
        logger.debug(f"Answer: {answer}")

        # Generate Answer Object
        source_documents = []
        for source in sources:
            source_document = SourceDocument(
                id=source.metadata["id"],
                content=source.page_content,
                title=source.metadata["title"],
                source=source.metadata["source"],
                chunk=source.metadata["chunk"],
                offset=source.metadata["offset"],
                page_number=source.metadata["page_number"],
            )
            source_documents.append(source_document)

        clean_answer = Answer(
            question=question,
            answer=answer,
            source_documents=source_documents,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
        )
        return clean_answer
