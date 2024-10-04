FROM python:3.12.5-slim

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY styling.py ./styling.py
COPY app.py ./app.py
COPY Citizens_Advice_Logo.png ./Citizens_Advice_Logo.png
COPY .env ./.env

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

ENTRYPOINT ["python", "app.py"]


# switch to building a trivial version of the app with fasthtml that can be accessed through app runner
# then introduce dynamo db dependency