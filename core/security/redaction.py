import re

_AUTH_VALUE = re.compile(r"(?i)\b(bearer|token)\s+[a-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|(?:api|access)[_-]?token|token|"
    r"(?:client|webhook)[_-]?secret|password|secret|credential)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_URL_USERINFO = re.compile(r"(https?://)([^/@\s]+)@", re.IGNORECASE)
_URL_SECRET_QUERY = re.compile(
    r"(?i)([?&](?:access[_-]?token|api[_-]?token|token|password|"
    r"client[_-]?secret|webhook[_-]?secret|secret|key)=)[^&\s]+"
)


def redact_sensitive_text(value: object, *, limit: int = 4000) -> str:
    text = str(value)
    text = _AUTH_VALUE.sub(r"\1 [REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", text)
    text = _URL_USERINFO.sub(r"\1[REDACTED]@", text)
    text = _URL_SECRET_QUERY.sub(r"\1[REDACTED]", text)
    return text[:limit]
