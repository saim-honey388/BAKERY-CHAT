"""Security helpers: PII masking and safe logging (minimal)."""

def mask_pii(text: str) -> str:
    # Very naive masking example
    import re
    masked = re.sub(r"\b\d{10,}\b", "[REDACTED]", text)
    return masked
