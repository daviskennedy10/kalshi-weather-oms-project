import base64
import time
from pathlib import Path

from cryptography.hazmat.primitives import (
    hashes,
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import (
    padding,
    rsa,
)


def auth_headers(
    key_id: str,
    private_key_path: str,
    request_path: str,
    *,
    timestamp_ms: int | None = None,
) -> dict[str, str]:
    """Create authentication headers for a GET request."""

    if not key_id:
        raise ValueError("Kalshi key_id cannot be empty.")

    path_without_query = request_path.split("?", maxsplit=1)[0]

    if not path_without_query.startswith("/"):
        raise ValueError(
            "Kalshi request_path must begin with '/'."
        )

    timestamp = str(
        timestamp_ms
        if timestamp_ms is not None
        else int(time.time() * 1000)
    )

    private_key = serialization.load_pem_private_key(
        Path(private_key_path).read_bytes(),
        password=None,
    )

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise TypeError(
            "Kalshi authentication requires an RSA private key."
        )

    message = (
        f"{timestamp}GET{path_without_query}".encode()
    )

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(
            signature
        ).decode(),
    }