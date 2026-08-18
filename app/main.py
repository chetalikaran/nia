from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import Conversation, analytics, classify_and_update, generate_reply
from .models import ChatRequest, ChatResponse

app = FastAPI(title="Northstar Homes Sales Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
conversations: dict[str, Conversation] = {}


@app.get("/")
def index():
    return FileResponse(Path("static/index.html"))


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    c = conversations.get(request.conversation_id or "") or Conversation()
    if c.ended:
        raise HTTPException(409, "This conversation has ended.")
    action = classify_and_update(c, request.message)
    c.messages.append({"role": "user", "content": request.message})
    reply = generate_reply(c, request.message, action)
    c.messages.append({"role": "assistant", "content": reply})
    conversations[c.id] = c
    return ChatResponse(conversation_id=c.id, reply=reply, memory=c.memory(), booking_status=c.booking_status, conversation_ended=c.ended)


@app.post("/api/conversations/{conversation_id}/end")
def end_conversation(conversation_id: str):
    c = conversations.get(conversation_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    c.ended = True
    return analytics(c)


@app.get("/api/conversations/{conversation_id}/analytics")
def get_analytics(conversation_id: str):
    c = conversations.get(conversation_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    return analytics(c)

