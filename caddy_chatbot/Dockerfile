FROM python:3.12.3

RUN pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml caddy_chatbot/src ./caddy_chatbot/

WORKDIR /caddy_chatbot

# Copy the necessary files
COPY pyproject.toml caddy_chatbot/src ./

# Install the dependencies
RUN poetry install

# Download the English model for spaCy using Python
RUN poetry run python -m spacy download en_core_web_sm


ENTRYPOINT ["poetry", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80", "--workers", "4"]
