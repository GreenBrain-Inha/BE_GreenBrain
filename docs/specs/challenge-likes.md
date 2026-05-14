# 챌린지 인증 사진 좋아요/좋아요 보상 Spec

## 1. 목적

인증 사진 좋아요 등록, 좋아요 3개 단위 milestone 보상, 좋아요 사용자 목록 조회 기능 계약을 정의한다. 이 문서는 좋아요와 좋아요 보상에 필요한 토큰 처리만 다룬다.

## 2. 담당 Owner

- Primary owner: 김찬혁
- Reviewer: 장태환
- Reviewer 지정 사유: 좋아요 milestone 보상은 `daily_token_state`와 `token_transactions`를 변경한다.

## 3. 관련 API

| Method | URL | 설명 |
| --- | --- | --- |
| `POST` | `/api/challenge-photos/{photo_id}/like` | 인증 사진 좋아요 등록 |
| `GET` | `/api/challenge-photos/{photo_id}/likes` | 좋아요 사용자 목록 조회 |

모든 API는 JWT 인증된 사용자만 호출할 수 있다.

## 4. Request / Response

### POST /api/challenge-photos/{photo_id}/like

#### Request

Body 없음.

#### Success Response

- Status: `201 Created`

```json
{
  "liked": true,
  "like_count": 3,
  "reward": {
    "reward_given": true,
    "reward_amount": 20,
    "milestone": 3,
    "tokens_remaining": 90
  }
}
```

좋아요는 성공했지만 보상 조건이 아닌 경우:

```json
{
  "liked": true,
  "like_count": 2,
  "reward": {
    "reward_given": false,
    "reward_amount": 0,
    "milestone": null,
    "tokens_remaining": 70
  }
}
```

milestone에는 도달했지만 일일 보상 상한 또는 토큰 잔액 상한 때문에 지급액이 0인 경우:

```json
{
  "liked": true,
  "like_count": 6,
  "reward": {
    "reward_given": true,
    "reward_amount": 0,
    "milestone": 6,
    "tokens_remaining": 150
  }
}
```

### GET /api/challenge-photos/{photo_id}/likes

#### Request

Query parameters:

| Name | Type | Required | Default | 설명 |
| --- | --- | --- | --- | --- |
| `limit` | integer | No | `50` | 반환 개수, 최대 100 |
| `cursor` | string | No | null | 다음 페이지 조회용 cursor |

#### Success Response

- Status: `200 OK`

```json
{
  "items": [
    {
      "user_id": "uuid",
      "nickname": "green-user",
      "profile_image_url": null,
      "liked_at": "2026-05-14T09:20:00Z"
    }
  ],
  "next_cursor": null
}
```

응답에는 이메일을 포함하지 않는다.

## 5. 주요 비즈니스 규칙

- 삭제되지 않은 인증 사진에만 좋아요할 수 있다.
- 본인이 업로드한 사진에는 본인이 좋아요할 수 없다.
- 같은 사용자는 같은 사진에 한 번만 좋아요할 수 있다.
- 계정 생성 후 24시간 이내 신규 계정은 좋아요 등록이 제한된다.
- 좋아요 등록 성공 후 누적 좋아요 수가 `3`, `6`, `9`처럼 3의 배수에 도달하면 milestone 보상 대상이 된다.
- 좋아요 milestone 보상은 사진 업로더에게 지급한다.
- milestone별 보상 기본값은 `+20` 토큰이다.
- 좋아요 보상은 KST 기준 업로더의 하루 보상 상한 `60` 토큰을 초과할 수 없다.
- 실제 지급액은 `min(20, 60 - like_reward_given_today, 150.0 - uploader_tokens_remaining)`으로 계산한다.
- 보상 상한 때문에 실제 지급액이 0이어도 해당 milestone은 처리된 것으로 기록할 수 있다.
- 이미 지급 또는 처리된 milestone은 중복 지급하지 않는다.
- 좋아요 보상 이력은 별도 `like_reward_log` 테이블 없이 `token_transactions`에 통합한다.
- 좋아요 사용자 목록은 `user_id`, `nickname`, `profile_image_url`, `liked_at`만 반환하고 이메일은 반환하지 않는다.

## 6. DB 영향 범위

- `likes`
  - 좋아요 등록 시 `photo_id`, `liker_user_id`, `created_at` 저장
  - `UNIQUE(photo_id, liker_user_id)`로 중복 좋아요 방지
- `challenge_photos`
  - 사진 존재 여부, 작성자, 삭제 여부 확인
  - 현재 DB 요약에 soft delete 컬럼이 없다면 좋아요 차단을 위해 `is_deleted`, `deleted_at` 컬럼과 migration이 필요하다.
- `users`
  - 좋아요 등록자의 계정 생성 시각으로 24시간 제한 확인
  - 좋아요 사용자 목록 표시용 프로필 정보 조회
- `daily_token_state`
  - 업로더의 KST 기준 오늘 row를 조회 또는 lazy initialize
  - `tokens_remaining`, `like_reward_given`, `total_reward_given`, `updated_at` 갱신
- `token_transactions`
  - milestone 보상 이력 저장
  - `type = like_reward`
  - `amount = 실제 지급액`
  - `source_type = photo`
  - `source_id = photo_id`
  - `milestone = 3 | 6 | 9 | ...`
  - `uq_token_transactions_like_reward_milestone` partial unique index로 중복 지급 방지

## 7. Service 책임

- `routers/`는 인증 사용자와 path parameter를 service에 전달한다.
- 사진 존재 여부, 삭제 여부, 자기 좋아요 금지, 중복 좋아요 금지, 신규 계정 제한은 service에서 검증한다.
- 좋아요 insert와 milestone 보상 계산은 같은 DB transaction 안에서 처리한다.
- milestone 계산은 좋아요 insert 후 현재 누적 수 기준으로 수행한다.
- 보상 지급 여부는 `token_transactions` unique partial index와 service 검증을 함께 사용해 동시성 중복 지급을 막는다.
- 보상 계산과 `daily_token_state` 갱신은 보상 service 경계에서 처리한다.
- 좋아요 사용자 목록 조회는 이메일과 민감 정보를 제외한 공개 프로필만 반환한다.

## 8. Error Cases

| Status | Code | 조건 |
| --- | --- | --- |
| `401 Unauthorized` | `UNAUTHORIZED` | 인증 쿠키가 없거나 유효하지 않음 |
| `404 Not Found` | `PHOTO_NOT_FOUND` | 사진이 존재하지 않거나 soft delete됨 |
| `409 Conflict` | `ALREADY_LIKED` | 같은 사용자가 이미 좋아요함 |
| `403 Forbidden` | `CANNOT_LIKE_OWN_PHOTO` | 본인 사진에 좋아요 시도 |
| `403 Forbidden` | `NEW_ACCOUNT_LIKE_RESTRICTED` | 계정 생성 후 24시간 이내 좋아요 시도 |
| `422 Unprocessable Entity` | `INVALID_PAGINATION` | 좋아요 사용자 목록 pagination 값이 유효하지 않음 |

## 9. Test Cases

- 다른 사용자의 삭제되지 않은 사진에 좋아요하면 `likes` row가 생성된다.
- 같은 사진에 중복 좋아요하면 `409 ALREADY_LIKED`를 반환한다.
- 본인 사진 좋아요는 `403 CANNOT_LIKE_OWN_PHOTO`를 반환한다.
- 계정 생성 후 24시간 이내 사용자의 좋아요는 `403 NEW_ACCOUNT_LIKE_RESTRICTED`를 반환한다.
- 삭제된 사진 좋아요는 `404 PHOTO_NOT_FOUND`를 반환한다.
- 좋아요 수가 3이 되면 업로더에게 `like_reward` transaction이 생성된다.
- 좋아요 수가 4 또는 5이면 보상이 생성되지 않는다.
- 좋아요 수가 6이 되면 milestone 6 보상이 생성된다.
- 같은 milestone에 대해 동시 요청이 들어와도 보상 transaction은 하나만 생성된다.
- 업로더의 `like_reward_given`이 50이면 milestone 보상 실제 지급액은 10이다.
- 업로더의 토큰 잔액이 145이면 실제 지급액은 5이다.
- 보상 상한으로 지급액이 0이어도 milestone 중복 지급은 발생하지 않는다.
- 좋아요 사용자 목록은 이메일을 포함하지 않는다.
- 좋아요 사용자 목록은 `liked_at` 기준 최신순 또는 명시된 정렬 정책에 따라 안정적으로 반환된다.

## 10. Frontend 연동 참고사항

- 피드 item의 `liked_by_me`가 true이면 좋아요 버튼을 비활성화한다.
- 본인 게시물의 좋아요 버튼은 비활성화한다.
- 좋아요 성공 후 응답의 `like_count`, `reward`, `tokens_remaining`으로 UI를 갱신한다.
- `reward.reward_given`이 true이고 `reward.reward_amount`가 0일 수 있으므로 보상 처리와 지급액 표시를 분리한다.
- `409 ALREADY_LIKED`는 UI 상태 불일치로 보고 좋아요 완료 상태로 동기화할 수 있다.
- 좋아요 사용자 목록 모달에는 이메일을 표시하지 않는다.
