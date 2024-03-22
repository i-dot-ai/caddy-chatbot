FROM public.ecr.aws/lambda/python:3.11

COPY . ./

RUN python3.11 -m pip install -r requirements.txt --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu

CMD ["answer.lambda_handler"]
