# 로그인 기능 Spec

## 개요 및 출처

이 문서는 이메일과 비밀번호 기반 로그인/로그아웃 기능의 구현 기준을 정의한다. 구현 범위는 GitHub Issue [#2 로그인/로그아웃 기능 구현](https://github.com/GreenBrain-Inha/BE_GreenBrain/issues/2)을 기준으로 하며, 다음 문서의 인증 요구사항을 따른다.

- `docs/references/PRD.md`: F-A03 로그인 / 로그아웃, JWT 기반 인증, 로그인 실패 잠금
- `docs/ARCHITECTURE.md`: `POST /api/auth/login`, `POST /api/auth/logout`, FastAPI JWT + bcrypt 구조
- `docs/ADR.md`: ADR-005 JWT를 HttpOnly 쿠키에 저장

## 기능 목표

- 사용자는 이메일과 비밀번호로 로그인할 수 있다.
- 로그인 성공 시 서버는 JWT를 `access_token` HttpOnly 쿠키로 발급한다.
- JWT 만료 시간은 7일로 설정한다.
- 비밀번호는 저장된 bcrypt 해시와 비교해 검증한다.
- 로그인 실패가 같은 이메일+IP 조합에서 5회를 초과하면 15분 동안 로그인을 잠근다.
- 사용자는 로그아웃할 수 있고, 로그아웃 시 인증 쿠키가 삭제된다.

## 제외 범위

- 회원가입 구현
- 이메일 인증 구현
- 소셜 로그인 구현
- 비밀번호 재설정 구현
- 온보딩 설문 구현
- `GET /api/users/me` 현재 사용자 조회 구현

## API 계약

### POST /api/auth/login

이메일과 비밀번호를 검증하고, 성공 시 JWT 인증 쿠키를 발급한다.

#### Request

```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```

#### Success Response

- Status: `200 OK`
- Body:

```json
{
  "message": "Login successful",
  "onboarding_completed": false
}
```

- Cookie:
  - Name: `access_token`
  - Value: JWT
  - Attributes: `HttpOnly`, `Secure`, `SameSite=Strict`, `Max-Age=604800`

`onboarding_completed`는 기존 `GET /api/users/me`와 동일하게 사용자 생활 습관 프로필 존재 여부로 판단한다.
로그인 성공 응답 body에는 그 외 사용자 정보를 포함하지 않는다. 현재 사용자 상세 정보는 별도 `GET /api/users/me`에서 조회한다.

#### Error Responses

존재하지 않는 이메일과 잘못된 비밀번호는 계정 존재 여부가 노출되지 않도록 동일한 응답을 반환한다.

```json
{
  "code": "INVALID_CREDENTIALS",
  "message": "Invalid email or password"
}
```

- Status: `401 Unauthorized`

로그인 실패 잠금 상태에서는 다음 응답을 반환한다.

```json
{
  "code": "LOGIN_TEMPORARILY_LOCKED",
  "message": "Too many failed login attempts. Try again later."
}
```

- Status: `429 Too Many Requests`

요청 body 형식이 잘못된 경우 FastAPI/Pydantic 기본 `422 Unprocessable Entity` 응답을 사용한다.

### POST /api/auth/logout

인증 쿠키를 만료시켜 로그아웃 처리한다.

#### Request

요청 body는 사용하지 않는다.

#### Success Response

- Status: `200 OK`
- Body:

```json
{
  "message": "Logout successful"
}
```

- Cookie:
  - `access_token` 쿠키를 만료 처리한다.

인증 쿠키가 없는 상태에서 호출해도 동일하게 성공 응답을 반환한다.

## 보안 및 상태 정책

- JWT는 localStorage에 저장하지 않고 `access_token` HttpOnly 쿠키로만 전달한다.
- 쿠키는 기본적으로 `HttpOnly`, `Secure`, `SameSite=Strict`를 사용한다.
- 프론트엔드와 백엔드가 서로 다른 도메인에 배포되는 경우 `docs/ARCHITECTURE.md`의 CORS 정책에 따라 `allow_credentials=True`, 명시적 `allowed_origins`, 필요 시 `SameSite=None; Secure`를 검토한다.
- JWT 만료 시간은 7일이다.
- JWT payload에는 사용자 식별에 필요한 최소 정보만 포함한다.
- 비밀번호는 평문 비교를 금지하고 bcrypt 해시 검증만 사용한다.
- 로그인 실패 횟수는 이메일+IP 조합 기준으로 기록한다.
- 같은 이메일+IP 조합에서 실패가 5회를 초과하면 15분 동안 로그인 요청을 차단한다.
- 잠금 상태에서는 올바른 비밀번호가 들어와도 로그인에 성공하지 않는다.
- 로그인 성공 시 해당 이메일+IP 조합의 실패 카운트를 초기화한다.
- 로그인 성공 응답의 `onboarding_completed`는 `user_profiles` 행이 있으면 `true`, 없으면 `false`다.
- `routers/`는 요청 검증과 service 호출만 담당하고, 인증 비즈니스 로직은 service 계층에 둔다.

## 테스트 및 인수 기준

- 올바른 이메일/비밀번호로 로그인하면 `200 OK`와 `Set-Cookie: access_token=...`이 반환된다.
- 온보딩 프로필이 없는 사용자가 로그인하면 `onboarding_completed: false`가 반환된다.
- 온보딩 프로필이 있는 사용자가 로그인하면 `onboarding_completed: true`가 반환된다.
- 로그인 성공 쿠키에는 `HttpOnly`, `Secure`, `SameSite=Strict`, 7일 만료 속성이 포함된다.
- 존재하지 않는 이메일은 `401 INVALID_CREDENTIALS`를 반환한다.
- 잘못된 비밀번호는 `401 INVALID_CREDENTIALS`를 반환한다.
- 존재하지 않는 이메일과 잘못된 비밀번호의 오류 형식은 동일하다.
- 같은 이메일+IP 조합에서 실패가 5회를 초과하면 `429 LOGIN_TEMPORARILY_LOCKED`를 반환한다.
- 잠금 상태에서는 올바른 비밀번호를 입력해도 로그인되지 않는다.
- 성공 로그인 후 해당 이메일+IP 조합의 실패 카운트가 초기화된다.
- 로그아웃 요청은 `200 OK`를 반환하고 `access_token` 쿠키를 만료시킨다.
- 인증 쿠키가 없는 상태에서 로그아웃해도 `200 OK`를 반환한다.
