def detect_intent(message: str):
    message = message.lower()

    intents = {
        "greeting": ["hi", "hello", "hey"],
        "password_reset": ["password", "reset", "forgot"],
        "order_status": ["order", "track", "delivery"],
        "refund_request": ["refund", "return", "money back"]
    }

    scores = {}

    for intent, keywords in intents.items():
        score = sum(1 for word in keywords if word in message)
        scores[intent] = score

    best_intent = max(scores, key=scores.get)
    confidence = scores[best_intent] / max(len(intents[best_intent]), 1)

    if message.isdigit():
        return "order_reference", 0.9

    if scores[best_intent] == 0:
        return "unknown", 0.0

    return best_intent, round(confidence, 2)


def generate_response(intent: str, confidence: float):

    if confidence < 0.3:
        return "I'm not fully confident about your request. Could you please provide more details?"

    if intent == "greeting":
        return "Hello! How can I help you today?"

    if intent == "password_reset":
        return "To reset your password, click on 'Forgot Password' on the login page."

    if intent == "order_status":
        return "Please share your order ID so I can help track your order."

    if intent == "refund_request":
        return "I can help with refunds. Please provide your order ID."

    if intent == "order_reference":
        return "Thanks! I have received your reference number. Our team will process it shortly."

    return "Sorry, I couldn’t understand your request. I’ll connect you to human support."
