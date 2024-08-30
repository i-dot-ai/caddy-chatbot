from langchain_community.chat_models import BedrockChat
from langchain_community.embeddings import BedrockEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_community.document_transformers import EmbeddingsClusteringFilter

from langchain.prompts import PromptTemplate

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from langchain.retrievers.document_compressors import DocumentCompressorPipeline

import boto3
from botocore.exceptions import NoCredentialsError
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from caddy_core.utils.monitoring import logger

import re
import os
from datetime import datetime
from typing import List, Tuple, Dict, Any

alternate_region = "eu-west-3"

opensearch_https = os.environ.get("OPENSEARCH_HTTPS")
embeddings = BedrockEmbeddings(
    model_id="cohere.embed-english-v3", region_name=alternate_region
)

try:
    session = boto3.Session()
    credentials = session.get_credentials()
    auth = AWS4Auth(
        region=alternate_region,
        service="aoss",
        refreshable_credentials=credentials,
    )
except NoCredentialsError:
    print("No credentials could be found")


class CaddyOpenSearchVectorSearch(OpenSearchVectorSearch):
    def similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = 5,
        **kwargs: Any,
    ) -> List[Tuple[Any, float]]:
        """
        Return docs and relevance scores
        """
        results = self.similarity_search_with_score(query, k=k, **kwargs)

        if not results:
            return []

        min_score = min(score for _, score in results)
        max_score = max(score for _, score in results)

        if max_score == min_score:
            return [(doc, 1.0) for doc, _ in results]

        return [
            (doc, (score - min_score) / (max_score - min_score))
            for doc, score in results
        ]


def build_chain(CADDY_PROMPT):
    caddy_retrievers = []

    for source in ["citizensadvice", "govuk", "advisernet"]:
        vectorstore = CaddyOpenSearchVectorSearch(
            index_name=f"{source}_scrape_db",
            opensearch_url=opensearch_https,
            embedding_function=embeddings,
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            attributes=["source", "raw_markdown"],
        )
        retriever = vectorstore.as_retriever(
            search_type="mmr", search_kwargs={"k": 6, "fetch_k": 18, "lambda_mult": 0.3}
        )
        caddy_retrievers.append(retriever)

    lotr = MergerRetriever(retrievers=caddy_retrievers)

    filter_ordered_by_retriever = EmbeddingsClusteringFilter(
        embeddings=embeddings,
        num_clusters=3,
        num_closest=2,
        sorted=True,
    )

    pipeline = DocumentCompressorPipeline(
        transformers=[filter_ordered_by_retriever])
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=pipeline, base_retriever=lotr
    )

    llm = BedrockChat(
        model_id=os.getenv("LLM"),
        region_name=alternate_region,
        model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
    )

    document_formatter = PromptTemplate(
        input_variables=["raw_markdown", "source"],
        template="Content:{raw_markdown}\nSOURCE_URL:{source}",
    )

    document_chain = create_stuff_documents_chain(
        llm, prompt=CADDY_PROMPT, document_prompt=document_formatter
    )
    chain = create_retrieval_chain(
        retriever=compression_retriever, combine_docs_chain=document_chain
    )

    ai_prompt_timestamp = datetime.now()
    return chain, ai_prompt_timestamp
