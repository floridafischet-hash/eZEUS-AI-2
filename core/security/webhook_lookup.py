import hashlib
import hmac

from core.config.settings import get_settings


class WebhookLookupKeyError(RuntimeError):
    pass


def webhook_secret_hmac(secret: str) -> str:
    key = get_settings().effective_webhook_lookup_hmac_key
    if not key:
        raise WebhookLookupKeyError("WEBHOOK_LOOKUP_HMAC_KEY is not configured")
    return hmac.new(key.encode(), secret.encode(), hashlib.sha256).hexdigest()
