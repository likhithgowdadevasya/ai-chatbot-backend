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
from db import chat_collection, users_collection, counters_collection

# --------------------------------
# App initialization
# --------------------------------
app = FastAPI(title="AI Customer Support Chatbot")

# --------------------------------
# Rate Limiter setup (PER USER / TOKEN)
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
# AUTH APIs (Signup & Login)
# --------------------------------
@app.post("/signup")
def signup(username: str, password: str):
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    user_id = get_next_user_id()
    hashed_password = hash_password(password)

    users_collection.insert_one({
        "user_id": user_id,
        "username": username,
        "password": hashed_password,
        "role": "user"   # ✅ DEFAULT ROLE
    })

    return {
        "message": "User registered successfully",
        "user_id": user_id,
        "role": "user"
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
        "role": user["role"]    # ✅ ROLE IN JWT
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
                detail="Access forbidden: insufficient permissions"
            )
        return current_user
    return role_checker

# --------------------------------
# Context Helper (Conversation Memory)
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
# Chat API (Protected + Rate Limited)
# --------------------------------
@app.post("/chat")
@limiter.limit("5/minute")   # ✅ RATE LIMIT
def chat(
    request: Request,
    chat_data: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    message = chat_data.message

    last_intent, _ = get_last_context(user_id)

    intent, confidence = detect_intent(message)

    if message.isdigit() and last_intent in ["refund_request", "order_status"]:
        intent = "order_reference"
        confidence = 0.9

    bot_reply = generate_response(intent, confidence)

    chat_collection.insert_one({
        "user_id": user_id,
        "user_message": message,
        "intent": intent,
        "confidence": confidence,
        "bot_reply": bot_reply,
        "timestamp": datetime.utcnow()
    })

    return {
        "user_id": user_id,
        "message": message,
        "intent": intent,
        "confidence": confidence,
        "bot_reply": bot_reply,
        "memory_used": last_intent is not None
    }

# --------------------------------
# Chat History API (Protected)
# --------------------------------
@app.get("/chat/history")
def get_chat_history(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    chats = chat_collection.find(
        {"user_id": user_id},
        {"_id": 0}
    )

    return {
        "user_id": user_id,
        "history": list(chats)
    }

# --------------------------------
# ADMIN APIs (RBAC)
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
