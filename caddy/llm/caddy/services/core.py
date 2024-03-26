from langchain_community.llms import Bedrock
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_community.document_transformers import EmbeddingsClusteringFilter

from langchain.chains import RetrievalQA
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.merger_retriever import MergerRetriever
from langchain.vectorstores.elasticsearch import ElasticsearchStore
from langchain.retrievers.document_compressors import DocumentCompressorPipeline

from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

import re
import os
import boto3
from typing import List, Any
from datetime import datetime

from caddy.utils.prompt import CORE_PROMPT

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()


@xray_recorder.capture()
def find_most_recent_caddy_vector_index():
    """Attempts to find one of the rolling Caddy vector indexes, and returns the most recent one.
    If no such index is found, the original index name is returned."""

    # Retrieve the original index name from the environment variable
    opensearch_index = os.environ.get("OPENSEARCH_INDEX")
    opensearch_https = os.environ.get("OPENSEARCH_HTTPS")
    credentials = boto3.Session().get_credentials()

    auth = AWS4Auth(
        service="es",
        region=os.environ.get("AWS_REGION"),
        refreshable_credentials=credentials,
    )

    embeddings = HuggingFaceEmbeddings(model_name="model")

    vectorstore = OpenSearchVectorSearch(
        index_name=opensearch_index,
        opensearch_url=opensearch_https,
        embedding_function=embeddings,
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    client = vectorstore.client

    # Initialize most_recent_index with the original index name as a fallback
    most_recent_index = opensearch_index

    # Pattern to match indexes of interest
    pattern = re.compile(r"caddy_vector_index_(\d{8})$")

    # Fetch all indexes
    index_list = client.cat.indices(format="json")
    most_recent_date = None

    for index_info in index_list:
        index_name = index_info["index"]
        match = pattern.match(index_name)
        if match:
            # Extract date from the index name
            extracted_date_str = match.group(1)
            try:
                extracted_date = datetime.strptime(extracted_date_str, "%Y%m%d")
                # Update most recent date and index name if this index is more recent
                if most_recent_date is None or extracted_date > most_recent_date:
                    most_recent_date = extracted_date
                    most_recent_index = index_name
            except ValueError:
                # If the date is not valid, ignore this index
                continue

    return most_recent_index


@xray_recorder.capture()
def build_chain():
    opensearch_index = find_most_recent_caddy_vector_index()
    opensearch_https = os.environ.get("OPENSEARCH_HTTPS")

    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(
        service="es",
        region=os.environ.get("AWS_REGION"),
        refreshable_credentials=credentials,
    )

    embeddings = HuggingFaceEmbeddings(model_name="../../model")

    vectorstore = OpenSearchVectorSearch(
        index_name=opensearch_index,
        opensearch_url=opensearch_https,
        embedding_function=embeddings,
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    advisernet_retriever = vectorstore.as_retriever(
        k="5",
        strategy=ElasticsearchStore.ApproxRetrievalStrategy(hybrid=True),
        search_kwargs={
            "filter": {"match": {"metadata.domain_description": "AdvisorNet"}}
        },
    )

    gov_retriever = vectorstore.as_retriever(
        k="5",
        strategy=ElasticsearchStore.ApproxRetrievalStrategy(hybrid=True),
        search_kwargs={"filter": {"match": {"metadata.domain_description": "GOV.UK"}}},
    )

    ca_retriever = vectorstore.as_retriever(
        k="5",
        strategy=ElasticsearchStore.ApproxRetrievalStrategy(hybrid=True),
        search_kwargs={
            "filter": {"match": {"metadata.domain_description": "Citizens Advice"}}
        },
    )

    lotr = MergerRetriever(
        retrievers=[gov_retriever, advisernet_retriever, ca_retriever]
    )

    filter_ordered_by_retriever = EmbeddingsClusteringFilter(
        embeddings=embeddings,
        num_clusters=3,
        num_closest=2,
        sorted=True,
        remove_duplicates=True,
    )

    pipeline = DocumentCompressorPipeline(transformers=[filter_ordered_by_retriever])
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=pipeline, base_retriever=lotr
    )

    llm = Bedrock(
        model_id="anthropic.claude-instant-v1",
        region_name="eu-central-1",
        model_kwargs={"temperature": 0.2, "max_tokens_to_sample": 750},
    )

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=compression_retriever,
        return_source_documents=True,
        chain_type_kwargs={
            "prompt": CORE_PROMPT,
        },
    )

    ai_prompt_timestamp = datetime.now()
    return chain, ai_prompt_timestamp


@xray_recorder.capture()
def run_chain(chain, prompt: str, history: List[Any]):
    ai_response = chain({"query": prompt, "chat_history": history})
    ai_response_timestamp = datetime.now()

    return ai_response, ai_response_timestamp
