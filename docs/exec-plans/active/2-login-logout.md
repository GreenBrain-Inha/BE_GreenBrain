# Issue #2: Login and Logout

## References

- GitHub Issue #2: `[FEATURE] 로그인/로그아웃 기능 구현`
- `docs/references/PRD.md`
- `docs/references/MVP_SCOPE.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/specs/login.md`
- `docs/specs/signup.md`
- `docs/generated/db-schema.md`

## Owner and Reviewer

- Primary owner: 장태환
- Reviewer: 김찬혁

## Scope

- Add login/logout Pydantic request and response schemas.
- Verify bcrypt password hashes created by signup.
- Issue a 7-day JWT in an `access_token` HttpOnly cookie on successful login.
- Track failed login attempts by normalized email and client IP.
- Lock login for 15 minutes after more than 5 failures.
- Clear the auth cookie on logout.
- Remove the previous harness structure from the repository.

## Out of Scope

- Signup changes beyond compatibility fixes.
- Current-user lookup API.
- Persistent login-attempt storage.
- Password reset, email verification, and social login.

## Implementation Steps

1. Remove legacy harness files and references.
2. Add focused API tests for login success, invalid credentials, lockout, reset-on-success, and logout.
3. Implement auth schemas, service logic, JWT creation, and router endpoints.
4. Run the auth tests and the full Python test suite.

## Test Plan

```bash
python3 -m pytest tests/test_auth_signup.py tests/test_auth_login.py
python3 -m pytest
```

## Review Checklist

- Router remains thin and delegates business logic to `services/auth.py`.
- Login errors do not reveal whether the email exists.
- Response bodies never expose password hashes or JWTs.
- Cookie attributes include `HttpOnly`, `Secure`, `SameSite=Strict`, and `Max-Age=604800`.
- Login lockout is scoped to normalized email plus client IP.
