# Full Pytest Suite — Result

- Timestamp: 2026-06-10T22:40:09Z
- Command: `docker compose run --rm ingestion python -m pytest tests/ -q`
- Image: Dockerfile.ingestion (deps baked in — no ad-hoc pip)
- Exit code: 0

```
1647 passed, 48 skipped, 6 warnings in 1526.24s (0:25:26)
```

## Tail of run
```
........................................................................ [ 89%]
........................................................................ [ 93%]
........................................................................ [ 97%]
...............s.......................                                  [100%]
=============================== warnings summary ===============================
../usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1
  /usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

backend/core/models.py:662
  /app/backend/core/models.py:662: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.13/migration/
    class OAuthToken(BaseModel):

tests/user_isolation/test_user_isolation.py::TestRequireCaseOwnerDependency::test_dependency_blocks_wrong_user
tests/user_isolation/test_user_isolation.py::TestRequireCaseOwnerDependency::test_dependency_allows_correct_user
  /usr/local/lib/python3.12/site-packages/jwt/api_jwt.py:147: InsecureKeyLengthWarning: The HMAC key is 11 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    return self._jws.encode(

tests/user_isolation/test_user_isolation.py::TestRequireCaseOwnerDependency::test_dependency_blocks_wrong_user
tests/user_isolation/test_user_isolation.py::TestRequireCaseOwnerDependency::test_dependency_allows_correct_user
  /usr/local/lib/python3.12/site-packages/jwt/api_jwt.py:368: InsecureKeyLengthWarning: The HMAC key is 11 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
    decoded = self.decode_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1647 passed, 48 skipped, 6 warnings in 1526.24s (0:25:26)
```
