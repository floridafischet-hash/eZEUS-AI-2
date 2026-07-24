from webhooks.paperless.security import verify_shared_secret


def test_verify_shared_secret() -> None:
    assert verify_shared_secret("secret", "secret") is True
    assert verify_shared_secret("wrong", "secret") is False
    assert verify_shared_secret(None, "secret") is False
