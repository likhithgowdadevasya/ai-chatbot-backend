from pymongo import MongoClient

MONGO_URI = "mongodb+srv://likhithgowdadevasya:Likhith150@cluster0.6ydko.mongodb.net/?appName=Cluster0"

client = MongoClient(MONGO_URI)

db = client["chatbot_db"]

chat_collection = db["chat_context"]
users_collection = db["users"]   # ✅ ADD THIS
counters_collection = db["counters"]