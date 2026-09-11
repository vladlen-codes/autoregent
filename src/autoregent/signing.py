import hashlib
import hmac

from .events import HealEvent


def sign_event(hmac_secret: str, event: HealEvent) -> str:
    """HMAC-SHA256 over the event record (minus the signature field itself).
    Proves the record wasn't tampered with after the fact -- not who wrote it;
    that needs asymmetric signing, which is your call to add for a real
    deployment (see EventStore for where persistence would plug in too)."""
    payload = event.model_dump_json(exclude={"signature"}).encode()
    return hmac.new(hmac_secret.encode(), payload, hashlib.sha256).hexdigest()
