FROM public.ecr.aws/lambda/python:3.11

COPY . ./

RUN python3.11 -m pip install -r requirements.txt --no-cache-dir

RUN spacy download en_core_web_sm

CMD ["conversations.lambda_handler"]
