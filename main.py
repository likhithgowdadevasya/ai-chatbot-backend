from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    Request
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime
from jose import JWTError, jwt

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# Auth utilities
from auth import hash_password, verify_password, create_access_token

# Chatbot logic
from chatbot import detect_intent, generate_response

# Database
from db import (
    chat_collection,
    users_collection,
    counters_collection,
    memory_collection
)

from ai_fallback import ai_fallback_response

# --------------------------------
# App initialization
# --------------------------------
app = FastAPI(title="AI Customer Support Chatbot")

# --------------------------------
# Rate Limiter setup
# --------------------------------
def user_key_func(request: Request):
    auth = request.headers.get("authorization")
    return auth if auth else get_remote_address(request)

limiter = Limiter(key_func=user_key_func)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please wait before sending more messages."}
    )

# --------------------------------
# JWT Configuration
# --------------------------------
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --------------------------------
# Root API
# --------------------------------
@app.get("/")
def root():
    return {"message": "AI Chatbot Backend is running successfully"}

# --------------------------------
# Request Models
# --------------------------------
class ChatRequest(BaseModel):
    message: str

# --------------------------------
# Small User ID Generator
# --------------------------------
def get_next_user_id():
    counter = counters_collection.find_one_and_update(
        {"_id": "user_id"},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    return f"u{counter['sequence_value']}"

# --------------------------------
# AUTH APIs
# --------------------------------
import os

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "admin123")


@app.post("/signup")
def signup(
    username: str,
    password: str,
    admin_key: str = None
):
    # Check existing user
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    user_id = get_next_user_id()
    hashed_password = hash_password(password)

    # -------------------------
    # Role Decision Logic
    # -------------------------
    if users_collection.count_documents({}) == 0:
        # First user → admin
        role = "admin"

    elif admin_key and admin_key == ADMIN_SECRET_KEY:
        # Admin secret key provided
        role = "admin"

    else:
        role = "user"

    # Save user
    users_collection.insert_one({
        "user_id": user_id,
        "username": username,
        "password": hashed_password,
        "role": role
    })

    return {
        "message": "User registered successfully",
        "user_id": user_id,
        "role": role
    }


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"username": form_data.username})

    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token({
        "sub": user["username"],
        "user_id": user["user_id"],
        "role": user["role"]
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

# --------------------------------
# JWT Validation Dependency
# --------------------------------
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return {
            "username": payload.get("sub"),
            "user_id": payload.get("user_id"),
            "role": payload.get("role")
        }

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# --------------------------------
# RBAC Dependency
# --------------------------------
def require_role(required_role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail="Access forbidden"
            )
        return current_user
    return role_checker

# --------------------------------
# Memory Helpers (NEW)
# --------------------------------
def get_recent_messages(user_id: str, limit=5):
    chats = chat_collection.find(
        {"user_id": user_id}
    ).sort("timestamp", -1).limit(limit)

    msgs = []
    for c in chats:
        msgs.append(f"User: {c['user_message']}")
        msgs.append(f"Bot: {c['bot_reply']}")

    msgs.reverse()
    return "\n".join(msgs)


def summarize_conversation(text: str):
    if not text:
        return ""
    lines = text.split("\n")
    return " | ".join(lines[-4:])


def update_memory(user_id: str):
    recent = get_recent_messages(user_id)
    summary = summarize_conversation(recent)

    memory_collection.update_one(
        {"user_id": user_id},
        {"$set": {"summary": summary}},
        upsert=True
    )


def get_memory(user_id: str):
    mem = memory_collection.find_one({"user_id": user_id})
    return mem["summary"] if mem else ""

# --------------------------------
# Context Helper
# --------------------------------
def get_last_context(user_id: str):
    chat = chat_collection.find_one(
        {"user_id": user_id},
        sort=[("timestamp", -1)]
    )
    if chat:
        return chat.get("intent"), chat.get("bot_reply")
    return None, None

# --------------------------------
# Chat API
# --------------------------------
@app.post("/chat")
@limiter.limit("5/minute")
def chat(
    request: Request,
    chat_data: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    message = chat_data.message

    memory_summary = get_memory(user_id)

    last_intent, _ = get_last_context(user_id)
    intent, confidence = detect_intent(message)

    if message.isdigit() and last_intent in ["refund_request", "order_status"]:
        intent = "order_reference"
        confidence = 0.9

    if confidence < 0.5 or intent == "unknown":
        bot_reply = ai_fallback_response(
            f"Conversation memory:\n{memory_summary}\nUser: {message}"
        )
        used_ai = True
    else:
        bot_reply = generate_response(intent, confidence)
        used_ai = False

    chat_collection.insert_one({
        "user_id": user_id,
        "user_message": message,
        "intent": intent,
        "confidence": confidence,
        "bot_reply": bot_reply,
        "ai_used": used_ai,
        "timestamp": datetime.utcnow()
    })

    update_memory(user_id)

    return {
        "user_id": user_id,
        "message": message,
        "intent": intent,
        "confidence": confidence,
        "bot_reply": bot_reply,
        "ai_used": used_ai,
        "memory_used": memory_summary != ""
    }

# --------------------------------
# Chat History API
# --------------------------------
@app.get("/chat/history")
def get_chat_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    chats = chat_collection.find({"user_id": user_id}, {"_id": 0})

    return {
        "user_id": user_id,
        "history": list(chats)
    }

# --------------------------------
# ADMIN APIs
# --------------------------------
@app.get("/admin/users")
def list_users(admin=Depends(require_role("admin"))):
    users = users_collection.find({}, {"_id": 0, "password": 0})
    return list(users)

@app.get("/admin/chat-stats")
def chat_stats(admin=Depends(require_role("admin"))):
    return {
        "total_users": users_collection.count_documents({}),
        "total_chats": chat_collection.count_documents({})
    }
@app.get("/admin/chats-per-user")
def chats_per_user(admin=Depends(require_role("admin"))):
    pipeline = [
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    results = chat_collection.aggregate(pipeline)

    return list(results)

@app.get("/admin/top-intents")
def top_intents(admin=Depends(require_role("admin"))):
    pipeline = [
        {"$group": {"_id": "$intent", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    results = chat_collection.aggregate(pipeline)

    return list(results)


@app.get("/admin/ai-usage")
def ai_usage(admin=Depends(require_role("admin"))):
    total = chat_collection.count_documents({})
    ai_used = chat_collection.count_documents({"ai_used": True})

    percent = (ai_used / total * 100) if total > 0 else 0

    return {
        "total_messages": total,
        "ai_responses": ai_used,
        "ai_usage_percent": round(percent, 2)
    }


@app.get("/admin/daily-chats")
def daily_chats(admin=Depends(require_role("admin"))):
    pipeline = [
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$timestamp"
                    }
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}}
    ]

    results = chat_collection.aggregate(pipeline)

    return list(results)
