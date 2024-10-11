FROM python:3.12.5-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt


COPY templates ./templates
COPY static ./static
COPY app.py ./app.py
COPY .env ./.env


EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

ENTRYPOINT ["python", "app.py"]
