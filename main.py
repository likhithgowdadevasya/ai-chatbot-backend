from fastapi import FastAPI
from pydantic import BaseModel
from ai_helper import ai_fallback_response


# Import chatbot logic
from chatbot import detect_intent, generate_response

app = FastAPI()

# -------------------------------
# In-memory chat context storage
# -------------------------------
# Format:
# {
#   "user_id": {
#       "last_intent": "refund_request"
#   }
# }
chat_context = {}

# -------------------------------
# Root API
# -------------------------------
@app.get("/")
def root():
    return {"message": "Backend is running successfully"}

# -------------------------------
# Hello API
# -------------------------------
@app.get("/hello")
def say_hello():
    return {"message": "Hello! Welcome to AI Customer Support Chatbot"}

# -------------------------------
# User Model & API
# -------------------------------
class User(BaseModel):
    name: str
    email: str

@app.post("/user")
def create_user(user: User):
    return {
        "status": "User created successfully",
        "user": user
    }

# -------------------------------
# Chat Request Model
# -------------------------------
class ChatRequest(BaseModel):
    user_id: str
    message: str

# -------------------------------
# Chatbot API (Context Aware)
# -------------------------------
@app.post("/chat")
def chat(request: ChatRequest):
    user_id = request.user_id
    message = request.message
    
   


    intent, confidence = detect_intent(message)
    
    # Use previous context if confidence is low
    if confidence < 0.3 and user_id in chat_context:
        intent = chat_context[user_id]["last_intent"]

    # Decide response source
    if intent == "unknown" or confidence < 0.3:
        bot_reply = ai_fallback_response(message)
    else:
        bot_reply = generate_response(intent, confidence)

    # Save conversation context
    chat_context[user_id] = {
        "last_intent": intent
    }
    

    return {
        "user_id": user_id,
        "user_message": message,
        "intent": intent,
        "confidence": confidence,
        "bot_reply": bot_reply,
        "response_type": "AI" if confidence < 0.3 else "Rule-based",
        "confidence_reason": "Rule-based match" if confidence >= 0.3 else "AI fallback due to low confidence"


    }
