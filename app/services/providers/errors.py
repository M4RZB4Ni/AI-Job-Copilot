def error_detail(error: Exception) -> str:
    """Pull the readable message out of an SDK error body, falling back to str(error)."""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict) and isinstance(inner.get("message"), str):
            return inner["message"]
        if isinstance(body.get("message"), str):
            return body["message"]
    return str(error)