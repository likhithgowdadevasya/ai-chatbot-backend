import ollama

def ai_fallback_response(message: str) -> str:
    try:
        response = ollama.chat(
            model="phi",  # or llama3
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful customer support assistant."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        return response["message"]["content"].strip()

    except Exception:
        return "AI service is temporarily unavailable. Please try again later."
