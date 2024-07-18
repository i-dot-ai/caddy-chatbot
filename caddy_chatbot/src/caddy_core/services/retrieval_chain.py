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

import re
import os
from datetime import datetime

alternate_region = "eu-west-3"

opensearch_https = os.environ.get("BEDROCK_OPENSEARCH_HTTPS")
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-image-v1", region_name=alternate_region
)

try:
    session = boto3.Session()
    credentials = session.get_credentials()
    auth = AWS4Auth(
        region=os.environ.get("AWS_REGION"),
        service="es",
        refreshable_credentials=credentials,
    )
except NoCredentialsError:
    print("No credentials could be found")


def find_most_recent_caddy_vector_index():
    """Attempts to find one of the rolling Caddy vector indexes, and returns the most recent one.
    If no such index is found, the original index name is returned."""

    # Retrieve the original index name from the environment variable
    opensearch_index = os.environ.get("BEDROCK_OPENSEARCH_INDEX")

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
    pattern = re.compile(opensearch_index + r"_(\d{8})$")

    # Fetch all indexes
    index_list = client.indices.get("*")
    most_recent_date = None

    for index_name in index_list:
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


def build_chain(CADDY_PROMPT):
    opensearch_index = find_most_recent_caddy_vector_index()

    vectorstore = OpenSearchVectorSearch(
        index_name=opensearch_index,
        opensearch_url=opensearch_https,
        embedding_function=embeddings,
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        attributes=["source_url"],
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

    llm = BedrockChat(
        model_id=os.environ.get("LLM"),
        region_name=alternate_region,
        model_kwargs={"temperature": 0.3, "top_k": 5, "max_tokens": 2000},
    )

    document_formatter = PromptTemplate(
        input_variables=["page_content", "source_url"],
        template="Content:{page_content}\nSOURCE_URL:{source_url}",
    )

    document_chain = create_stuff_documents_chain(
        llm, prompt=CADDY_PROMPT, document_prompt=document_formatter
    )
    chain = create_retrieval_chain(
        retriever=compression_retriever, combine_docs_chain=document_chain
    )

    ai_prompt_timestamp = datetime.now()
    return chain, ai_prompt_timestamp
