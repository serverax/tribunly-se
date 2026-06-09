"""
Integration test conftest.
Skips tests that require external services (AWS, JWKS, KMS) when not configured.
"""
import os
import pytest


def pytest_collection_modifyitems(items):
    """Skip integration tests that require AWS/boto3 when not configured."""
    skip_aws = pytest.mark.skip(reason="AWS/boto3 not configured — set AWS_ACCESS_KEY_ID")
    skip_kms = pytest.mark.skip(reason="KMS not configured — set KEY_MANAGEMENT_MODE=aws_kms")

    for item in items:
        # KMS tests require boto3
        if "kms" in item.nodeid.lower() or "envelope" in item.nodeid.lower():
            try:
                import boto3  # noqa
            except ImportError:
                item.add_marker(skip_aws)
                continue
        # JWT/JWKS tests
        if "jwks" in item.nodeid.lower():
            if not os.environ.get("JWT_JWKS_URL"):
                item.add_marker(pytest.mark.skip(reason="JWT_JWKS_URL not configured"))
