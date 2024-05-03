from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from typing import List
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain_core.language_models.chat_models import BaseChatModel
import ast


class LLMPriorityRetriever(BaseRetriever):
    """Retriever that merges the results of multiple retrievers."""

    retriever_list: List[BaseRetriever]
    llm: BaseChatModel
    alternative_retriever: BaseRetriever
    max_document_length: int = 500
    max_retrieved_documents: int = 6

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        lotr = MergerRetriever(retrievers=self.retriever_list)
        all_relevant_docs = lotr.get_relevant_documents(query)

        all_docs = [
            (
                (index, document.page_content[: self.max_document_length])
                if len(document.page_content) > self.max_document_length
                else (index, document.page_content)
            )
            for index, document in enumerate(all_relevant_docs)
        ]

        document_prioritisation_prompt = f"""Please read the documents below, and rank them in order of relevance to this query: '{query}'. Please rank them in order of relevance, with 1 being the most relevant, and 5 being the least relevant. Please separate your rankings with a comma, in the format of a Python list. For example, if you think document 1 is the most relevant, and document 5 is the least relevant, please enter: [1, 2, 3, 4, 5]. Return only the list with no other output.

            Documents: {all_docs}

            Remember to return only your list, with no other output or context."""

        llm_priority = self.llm.predict(document_prioritisation_prompt)

        response_as_list = ast.literal_eval(llm_priority)

        try:
            # get the top 5 documents
            top_docs = [
                all_relevant_docs[index]
                for index in response_as_list[: self.max_retrieved_documents]
            ]

        except Exception:
            # if it fails, return all the docs
            top_docs = self.alternative_retriever.get_relevant_documents(query)

        return top_docs
