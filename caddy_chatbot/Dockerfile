FROM --platform=linux/amd64 python:3.12-slim

RUN pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml caddy_chatbot/src ./caddy_chatbot/

WORKDIR /caddy_chatbot

RUN poetry install

RUN spacy download en_core_web_sm

ENTRYPOINT ["poetry", "run", "uvicorn", "caddy:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]