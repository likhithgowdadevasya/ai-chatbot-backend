def ai_fallback_response(message: str):
    """
    AI fallback with safety and professionalism.
    """

    prompt = (
        "You are a professional customer support assistant. "
        "Respond clearly, politely, and concisely. "
        "If the issue requires human assistance, suggest contacting support.\n\n"
        f"User message: {message}"
    )

    # Mock AI response (safe & deterministic)
    return (
        "I understand your issue. "
        "Please try restarting the application and checking your login details. "
        "If the problem persists, our support team will be happy to assist you."
    )
