from langchain_aws import ChatBedrock
from langchain_community.embeddings import BedrockEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_community.document_transformers import EmbeddingsClusteringFilter

from langchain.prompts import PromptTemplate

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.retrievers.document_compressors import DocumentCompressorPipeline

import boto3
from botocore.exceptions import NoCredentialsError
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from caddy_core.utils.monitoring import logger
from caddy_core.services.enrolment import check_user_sources

import os
from datetime import datetime
from typing import List, Tuple, Any

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


def build_chain(CADDY_PROMPT, user: str = None):
    caddy_retrievers = []

    source_list = check_user_sources(user)

    sources = len(source_list)
    total_source_docs = 6
    input_docs_per_source = total_source_docs * 2
    fetched_docs_per_source = total_source_docs * 3
    filtered_docs_per_source = round(total_source_docs / sources)
    logger.debug(f"Sources: {sources}")
    logger.debug(f"Total source docs: {total_source_docs}")
    logger.debug(f"Total input docs: {input_docs_per_source * sources}")
    logger.debug(f"Total fetched docs: {fetched_docs_per_source * sources}")
    logger.debug(f"Total filtered docs: {filtered_docs_per_source * sources}")

    for source in source_list:
        vectorstore = CaddyOpenSearchVectorSearch(
            index_name=f"{source}_scrape_db",
            opensearch_url=opensearch_https,
            embedding_function=embeddings,
            http_auth=auth,
            timeout=3000,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            attributes=["source", "raw_markdown"],
        )
        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": input_docs_per_source,
                "fetch_k": fetched_docs_per_source,
                "lambda_mult": 0.2,
            },
        )
        caddy_retrievers.append(retriever)

    lotr = MergerRetriever(retrievers=caddy_retrievers)

    filter_ordered_by_retriever = EmbeddingsClusteringFilter(
        embeddings=embeddings,
        num_clusters=sources,
        num_closest=filtered_docs_per_source,
        sorted=True,
    )

    pipeline = DocumentCompressorPipeline(transformers=[filter_ordered_by_retriever])
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=pipeline, base_retriever=lotr
    )

    llm = ChatBedrock(
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
