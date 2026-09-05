import hashlib
import hmac

from app.config import settings
from app.events import HealEvent


def sign_event(event: HealEvent) -> str:
    """HMAC-SHA256 over the event record (minus the signature field itself).
    Proves the record wasn't tampered with after the fact -- not who wrote it;
    that needs asymmetric signing, out of scope for v0.1."""
    payload = event.model_dump_json(exclude={"signature"}).encode()
    return hmac.new(settings.hmac_secret.encode(), payload, hashlib.sha256).hexdigest()
