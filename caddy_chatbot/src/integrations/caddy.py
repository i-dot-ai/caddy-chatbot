from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse

from .integrations.google_chat.verification import verify_google_chat_request, verify_google_chat_supervision_request

app = FastAPI(
    docs_url=None
)

@app.get('/')
def root():
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})

@app.post('/google-chat/chat')
def handle_google_chat_request(request: Request = Depends(verify_google_chat_request)):
    return JSONResponse(status_code=200, content={"text": "Request received"})

@app.post('/google-chat/supervision')
def handle_google_chat_request(request: Request = Depends(verify_google_chat_supervision_request)):
    return JSONResponse(status_code=200, content={"text": "Request received"})

@app.post('/microsoft-teams/chat')
def handle_google_chat_request(request: Request):
    return JSONResponse(status_code=200, content={"text": "Request received"})

@app.post('/microsoft-teams/supervision')
def handle_google_chat_request(request: Request):
    return JSONResponse(status_code=200, content={"text": "Request received"})

@app.post('/caddy/chat')
def handle_google_chat_request(request: Request):
    return JSONResponse(status_code=200, content={"text": "Request received"})

@app.post('/caddy/supervision')
def handle_google_chat_request(request: Request):
    return JSONResponse(status_code=200, content={"text": "Request received"})
