from datasets import Dataset
from langchain_openai.chat_models import AzureChatOpenAI
from langchain_openai.embeddings import AzureOpenAIEmbeddings
from ragas import evaluate
import dotenv

from ragas.metrics import (
    context_precision,
    answer_relevancy,
    faithfulness,
    context_recall,
)

from model_answers import questions, ground_truths, contexts, answers

questions_mini = questions
ground_truths_mini = ground_truths
contexts_mini = contexts
answers_mini = answers

from model_answers_bedrock import questions, ground_truths, context, answers

questions_bedrock = questions
ground_truths_bedrock = ground_truths
contexts_bedrock = contexts
answers_bedrock = answers


def create_ragas_dataset(questions, ground_truths, contexts, answers):
    data_samples = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }
    dataset = Dataset.from_dict(data_samples)

    return dataset


bedrock_ragas_dataset = create_ragas_dataset(
    questions_bedrock, answers_bedrock, contexts_bedrock, ground_truths_bedrock
)
mini_ragas_dataset = create_ragas_dataset(
    questions_mini, answers_mini, contexts_mini, ground_truths_mini
)

ENV = dotenv.dotenv_values()

azure_model = AzureChatOpenAI(
    api_key=ENV["AZURE_OPENAI_API_KEY"],
    openai_api_version=ENV["OPENAI_API_VERSION"],
    azure_endpoint=ENV["AZURE_OPENAI_ENDPOINT"],
    model=ENV["AZURE_OPENAI_DEPLOYMENT_NAME"],
    validate_base_url=False,
)

# init the embeddings for answer_relevancy, answer_correctness and answer_similarity
azure_embeddings = AzureOpenAIEmbeddings(
    api_key=ENV["AZURE_EMBEDDING_API_KEY"],
    azure_endpoint=ENV["AZURE_EMBEDDING_ENDPOINT"],
    azure_deployment=ENV["EMBEDDING_DEPLOYMENT_NAME"],
)

# list of metrics we're going to use
metrics = [
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
]

import time
import requests
from ratelimit import limits, sleep_and_retry
from requests.exceptions import HTTPError

# Define your rate limit (e.g., 5 requests per minute)
RATE_LIMIT = 5
TIME_PERIOD = 60  # seconds


def ragas_evaluate(dataset, model, embeddings):
    result = evaluate(
        dataset,
        metrics=[answer_relevancy],
        llm=model,
        embeddings=embeddings,
        is_async=True,
        # max_concurrent=1  # Add this line
    )

    return result


print(ragas_evaluate(bedrock_ragas_dataset, azure_model, azure_embeddings))
print(ragas_evaluate(mini_ragas_dataset, azure_model, azure_embeddings))
