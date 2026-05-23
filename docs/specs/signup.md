# 회원가입 기능 Spec

## 개요 및 출처

이 문서는 이메일과 비밀번호 기반 회원가입 기능의 구현 기준을 정의한다. 구현 범위는 GitHub Issue [#1 회원가입 기능 구현](https://github.com/GreenBrain-Inha/BE_GreenBrain/issues/1)을 기준으로 하며, 다음 문서의 인증 요구사항을 따른다.

- `docs/references/PRD.md`: F-A01 회원가입, 비밀번호 보안 요구사항
- `docs/ARCHITECTURE.md`: `POST /api/auth/signup`, `users` 테이블, FastAPI JWT + bcrypt 구조

## 기능 목표

- 사용자는 이메일과 비밀번호로 회원가입할 수 있다.
- 서버는 이메일을 정규화해 저장하고, 정규화된 이메일 기준으로 중복 가입을 방지한다.
- 비밀번호는 최소 8자, 대문자 1개 이상, 소문자 1개 이상, 숫자 1개 이상이어야 하며 UTF-8 인코딩 기준 72 bytes를 초과할 수 없다.
- 비밀번호는 평문으로 저장하지 않고 bcrypt 해시로 저장한다.
- 회원가입 성공 시 `users` 테이블에 신규 사용자를 생성한다.

## 제외 범위

- 로그인 구현
- JWT 쿠키 발급
- 로그아웃 구현
- 이메일 인증 구현
- 소셜 로그인 구현
- 비밀번호 재설정 구현
- 온보딩 설문 구현
- `GET /api/users/me` 현재 사용자 조회 구현

## API 계약

### POST /api/auth/signup

이메일과 비밀번호를 검증하고 신규 사용자를 생성한다.

#### Request

```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```

#### Success Response

- Status: `201 Created`
- Body:

```json
{
  "message": "Signup successful",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "onboarding_completed": false,
    "created_at": "2026-05-11T00:00:00Z"
  }
}
```

회원가입 성공 후 자동 로그인은 하지 않는다. 응답에 `Set-Cookie`를 포함하지 않고, JWT 쿠키 발급은 로그인 기능에서 처리한다.
`onboarding_completed`는 회원가입 직후 항상 `false`다.

#### Error Responses

이미 가입된 이메일이면 다음 응답을 반환한다.

```json
{
  "code": "EMAIL_ALREADY_EXISTS",
  "message": "Email already exists"
}
```

- Status: `409 Conflict`

비밀번호 정책을 만족하지 못하면 bcrypt 해시 전에 다음 응답을 반환한다.

```json
{
  "code": "PASSWORD_POLICY_VIOLATION",
  "message": "Password must be at least 8 characters, include uppercase, lowercase, and number, and be at most 72 bytes"
}
```

- Status: `422 Unprocessable Entity`

요청 body 형식이 잘못되었거나 이메일 형식이 유효하지 않은 경우 FastAPI/Pydantic 기본 `422 Unprocessable Entity` 응답을 사용한다.

## 보안 및 상태 정책

- 이메일은 저장 전에 앞뒤 공백을 제거하고 lowercase로 정규화한다.
- 이메일 중복 검사는 정규화된 이메일 기준으로 수행한다.
- 동시 회원가입 요청으로 `users.email` unique constraint 위반이 발생하면 사전 중복 검사와 동일하게 `409 EMAIL_ALREADY_EXISTS`로 변환한다.
- `users.email`은 정규화된 이메일만 저장한다.
- 비밀번호는 평문 저장을 금지하고 bcrypt 해시만 `users.password_hash`에 저장한다.
- 비밀번호 정책 검증은 bcrypt 해시 전에 수행하며, UTF-8 인코딩 기준 72 bytes 초과 비밀번호는 `PASSWORD_POLICY_VIOLATION`으로 거부한다.
- 응답 body에는 `password`, `password_hash`를 포함하지 않는다.
- 회원가입 성공은 인증 상태를 만들지 않는다.
- `routers/`는 요청 검증과 service 호출만 담당하고, 이메일 중복 검사, 비밀번호 정책 검증, bcrypt 해시 저장은 service 계층에서 처리한다.

## 테스트 및 인수 기준

- 유효한 이메일/비밀번호로 요청하면 `201 Created`와 `id`, `email`, `onboarding_completed`, `created_at`, `message`가 반환된다.
- 회원가입 성공 시 `users` 테이블에 신규 사용자 행이 생성된다.
- 저장된 `password_hash`는 평문 비밀번호와 다르고 bcrypt 검증이 가능하다.
- 이메일은 앞뒤 공백 제거 및 lowercase 정규화 후 저장된다.
- 동일 이메일을 대소문자만 다르게 다시 가입하면 `409 EMAIL_ALREADY_EXISTS`를 반환한다.
- 동시 가입 경쟁으로 DB unique constraint 위반이 발생해도 `409 EMAIL_ALREADY_EXISTS`를 반환한다.
- 8자 미만 비밀번호는 `422 PASSWORD_POLICY_VIOLATION`를 반환한다.
- 대문자가 없는 비밀번호는 `422 PASSWORD_POLICY_VIOLATION`를 반환한다.
- 소문자가 없는 비밀번호는 `422 PASSWORD_POLICY_VIOLATION`를 반환한다.
- 숫자가 없는 비밀번호는 `422 PASSWORD_POLICY_VIOLATION`를 반환한다.
- UTF-8 인코딩 기준 72 bytes를 초과하는 비밀번호는 bcrypt 해시를 시도하지 않고 `422 PASSWORD_POLICY_VIOLATION`를 반환한다.
- 응답 body에는 `password`, `password_hash`가 포함되지 않는다.
- 회원가입 성공 응답에는 `Set-Cookie`가 포함되지 않는다.
