def safe_replace(text: str | None) -> str | None:
    return text.replace('\'', ' ') if text else None
