import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import (
    hashes,
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import (
    padding,
    rsa,
)

from weather_oms.ingest.kalshi_auth import auth_headers


def write_private_key(path: Path) -> rsa.RSAPrivateKey:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=(
                serialization.NoEncryption()
            ),
        )
    )

    return private_key


def test_creates_valid_get_signature(
    tmp_path: Path,
) -> None:
    key_path = tmp_path / "kalshi.key"
    private_key = write_private_key(key_path)

    headers = auth_headers(
        key_id="test-key",
        private_key_path=str(key_path),
        request_path=(
            "/trade-api/v2/portfolio/orders?limit=5"
        ),
        timestamp_ms=1_700_000_000_000,
    )

    assert headers["KALSHI-ACCESS-KEY"] == "test-key"
    assert (
        headers["KALSHI-ACCESS-TIMESTAMP"]
        == "1700000000000"
    )

    signature = base64.b64decode(
        headers["KALSHI-ACCESS-SIGNATURE"]
    )

    private_key.public_key().verify(
        signature,
        (
            b"1700000000000"
            b"GET"
            b"/trade-api/v2/portfolio/orders"
        ),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )


def test_rejects_empty_key_id(tmp_path: Path) -> None:
    key_path = tmp_path / "kalshi.key"
    write_private_key(key_path)

    with pytest.raises(
        ValueError,
        match="key_id cannot be empty",
    ):
        auth_headers(
            key_id="",
            private_key_path=str(key_path),
            request_path="/trade-api/ws/v2",
        )


def test_rejects_invalid_request_path(
    tmp_path: Path,
) -> None:
    key_path = tmp_path / "kalshi.key"
    write_private_key(key_path)

    with pytest.raises(
        ValueError,
        match="must begin",
    ):
        auth_headers(
            key_id="test-key",
            private_key_path=str(key_path),
            request_path="trade-api/ws/v2",
        )