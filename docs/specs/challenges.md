# 챌린지 생성/조회/수락 Spec

## 1. 목적

토큰 소진 후 사용자가 탄소 절감 챌린지를 생성, 조회, 수락하는 기능 계약을 정의한다. 이 문서는 김찬혁 담당 영역 중 챌린지 생성과 챌린지 조회/수락만 다루며, 채팅, 로그인, 회원가입, 온보딩 구현 상세는 포함하지 않는다.

## 2. 담당 Owner

- Primary owner: 김찬혁
- Reviewer: 장태환
- Reviewer 지정 사유: 챌린지 생성 조건이 `daily_token_state`와 토큰 소진 상태에 의존한다.

## 3. 관련 API

| Method | URL | 설명 |
| --- | --- | --- |
| `GET` | `/api/challenges/current` | 현재 사용자의 진행 중 챌린지 조회 |
| `POST` | `/api/challenges/generate` | 토큰 소진 상태에서 챌린지 자동 생성 |
| `POST` | `/api/challenges/{id}/accept` | 생성된 챌린지 수락 |

모든 API는 JWT 인증된 사용자만 호출할 수 있다.

## 4. Request / Response

### GET /api/challenges/current

#### Request

Body 없음.

#### Success Response

- Status: `200 OK`

진행 중인 챌린지가 있는 경우:

```json
{
  "challenge": {
    "id": "uuid",
    "category": "transport",
    "title": "대중교통으로 이동하기",
    "description": "오늘 한 번은 자가용 대신 대중교통이나 도보를 이용합니다.",
    "difficulty": 1,
    "status": "pending_acceptance",
    "created_at": "2026-05-14T09:00:00Z",
    "completed_at": null
  }
}
```

진행 중인 챌린지가 없는 경우:

```json
{
  "challenge": null
}
```

### POST /api/challenges/generate

#### Request

Body 없음.

#### Success Response

- Status: `201 Created` 또는 기존 미완료 챌린지 반환 시 `200 OK`

```json
{
  "challenge": {
    "id": "uuid",
    "category": "diet",
    "title": "오늘 한 끼 채식하기",
    "description": "오늘 한 끼는 고기 없이 채식 위주로 식사합니다.",
    "difficulty": 1,
    "status": "pending_acceptance",
    "created_at": "2026-05-14T09:00:00Z",
    "completed_at": null
  },
  "created": true
}
```

### POST /api/challenges/{id}/accept

#### Request

Body 없음.

#### Success Response

- Status: `200 OK`

```json
{
  "challenge": {
    "id": "uuid",
    "category": "diet",
    "title": "오늘 한 끼 채식하기",
    "description": "오늘 한 끼는 고기 없이 채식 위주로 식사합니다.",
    "difficulty": 1,
    "status": "active",
    "created_at": "2026-05-14T09:00:00Z",
    "completed_at": null
  }
}
```

## 5. 주요 비즈니스 규칙

- 챌린지는 토큰 소진 상태에서만 새로 생성할 수 있다.
- 사용자는 한 번에 하나의 `pending_acceptance` 또는 `active` 챌린지만 가질 수 있다.
- 기존 미완료 챌린지가 있으면 새 챌린지를 만들지 않고 기존 챌린지를 반환한다.
- 사용자당 KST 기준 하루 최대 3개까지만 챌린지를 생성할 수 있다.
- 챌린지 생성 시 `daily_token_state.challenge_count`를 증가시킨다.
- 챌린지 최초 상태는 `pending_acceptance`다.
- 사용자가 수락하면 상태를 `active`로 변경한다.
- `active` 챌린지는 인증 사진 업로드가 완료되면 `completed`가 된다.
- 카테고리는 `transport`, `diet`, `energy` 중 하나를 사용한다.
- 난이도는 `1`, `2`, `3` 범위를 사용하며, 누적 완료 이력에 따라 점진 상승할 수 있다.
- 챌린지 자동 생성은 생활 습관 프로필과 기존 챌린지 이력을 참고하되, OpenAI 호출은 `services/`에서만 수행한다.

## 6. DB 영향 범위

- `challenges`
  - 생성 시 `user_id`, `category`, `title`, `description`, `difficulty`, `status` 저장
  - 수락 시 `status = active`로 변경
  - 완료는 사진 업로드 spec에서 `status = completed`, `completed_at` 갱신
  - `status IN ('pending_acceptance', 'active')` 조건의 사용자별 미완료 챌린지 unique partial index를 따른다.
- `daily_token_state`
  - KST 기준 오늘 row를 조회 또는 lazy initialize
  - 새 챌린지 생성 시 `challenge_count` 증가
- `user_profiles`
  - 챌린지 생성 입력 컨텍스트로 조회한다.
- `token_transactions`
  - 이 spec에서는 직접 생성하지 않는다.

## 7. Service 책임

- `routers/`는 인증 사용자 확인, 경로 파라미터 전달, schema 변환만 담당한다.
- 챌린지 생성 가능 여부, 중복 방지, 일일 상한 검증은 service에서 처리한다.
- OpenAI 기반 챌린지 생성은 `services/challenge_gen.py` 경계 안에서 처리한다.
- `daily_token_state` 조회, 생성, `challenge_count` 변경은 transaction 안에서 처리한다.
- 소유권 검증은 service에서 수행한다.
- API 응답 DTO는 `schemas/`의 Pydantic schema를 사용한다.

## 8. Error Cases

| Status | Code | 조건 |
| --- | --- | --- |
| `401 Unauthorized` | `UNAUTHORIZED` | 인증 쿠키가 없거나 유효하지 않음 |
| `403 Forbidden` | `CHALLENGE_NOT_OWNED` | 다른 사용자의 챌린지를 수락하려 함 |
| `404 Not Found` | `CHALLENGE_NOT_FOUND` | 챌린지가 존재하지 않음 |
| `409 Conflict` | `CHALLENGE_NOT_PENDING` | `pending_acceptance` 상태가 아닌 챌린지를 수락하려 함 |
| `409 Conflict` | `TOKEN_NOT_EXHAUSTED` | 토큰이 아직 소진되지 않았는데 새 챌린지를 생성하려 함 |
| `429 Too Many Requests` | `DAILY_CHALLENGE_LIMIT_REACHED` | KST 기준 하루 챌린지 생성 수가 3개에 도달함 |
| `502 Bad Gateway` | `CHALLENGE_GENERATION_FAILED` | 챌린지 생성 외부 호출 또는 생성 결과 파싱 실패 |

## 9. Test Cases

- 토큰 소진 상태에서 `POST /api/challenges/generate` 호출 시 `pending_acceptance` 챌린지가 생성된다.
- 토큰이 남아 있으면 챌린지 생성이 거부된다.
- 기존 `pending_acceptance` 챌린지가 있으면 새 row를 만들지 않고 기존 챌린지를 반환한다.
- 기존 `active` 챌린지가 있으면 새 row를 만들지 않고 기존 챌린지를 반환한다.
- KST 기준 `challenge_count`가 3이면 새 챌린지 생성이 거부된다.
- `GET /api/challenges/current`는 `pending_acceptance` 또는 `active` 챌린지를 반환한다.
- 현재 챌린지가 없으면 `challenge: null`을 반환한다.
- 본인 챌린지를 수락하면 상태가 `active`로 변경된다.
- 다른 사용자의 챌린지 수락은 `403`을 반환한다.
- 이미 `active` 또는 `completed`인 챌린지 수락은 `409`를 반환한다.

## 10. Frontend 연동 참고사항

- 토큰 소진 후 `/challenges` 화면에서 `GET /api/challenges/current`를 먼저 호출한다.
- 현재 챌린지가 없을 때만 `POST /api/challenges/generate`를 호출한다.
- `pending_acceptance` 상태에서는 수락 버튼을 노출한다.
- `active` 상태에서는 인증 사진 업로드 UI를 노출한다.
- `completed` 상태는 현재 챌린지로 취급하지 않고 피드 또는 완료 상태로 안내한다.
- 챌린지 생성 실패 시 채팅 기능이나 인증 기능을 직접 호출하지 않는다.
