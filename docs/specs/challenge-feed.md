# 챌린지 인증 피드/Soft Delete Spec

## 1. 목적

챌린지 인증 사진이 업로드된 게시물을 최신순 피드로 조회하고, 본인 피드 게시물을 soft delete하는 기능 계약을 정의한다. 이 문서는 인증 피드 조회와 피드 게시물 soft delete만 다룬다.

## 2. 담당 Owner

- Primary owner: 김찬혁
- Reviewer: 장태환

## 3. 관련 API

| Method | URL | 설명 |
| --- | --- | --- |
| `GET` | `/api/challenges/feed` | 인증 피드 목록 최신순 조회 |
| `DELETE` | `/api/challenge-photos/{photo_id}` | 본인 인증 피드 게시물 soft delete |

모든 API는 JWT 인증된 사용자만 호출할 수 있다.

## 4. Request / Response

### GET /api/challenges/feed

#### Request

Query parameters:

| Name | Type | Required | Default | 설명 |
| --- | --- | --- | --- | --- |
| `limit` | integer | No | `20` | 반환 개수, 최대 50 |
| `cursor` | string | No | null | 다음 페이지 조회용 cursor |

#### Success Response

- Status: `200 OK`

```json
{
  "items": [
    {
      "photo_id": "uuid",
      "challenge_id": "uuid",
      "challenge_title": "오늘 한 끼 채식하기",
      "challenge_category": "diet",
      "file_url": "https://storage.example.com/challenge-photos/uuid.webp",
      "author": {
        "user_id": "uuid",
        "nickname": "green-user",
        "profile_image_url": null
      },
      "like_count": 2,
      "liked_by_me": false,
      "created_at": "2026-05-14T09:10:00Z"
    }
  ],
  "next_cursor": "opaque-cursor"
}
```

### DELETE /api/challenge-photos/{photo_id}

#### Request

Body 없음.

#### Success Response

- Status: `200 OK`

```json
{
  "deleted": true
}
```

이미 삭제된 게시물은 멱등 처리를 위해 `200 OK`와 `deleted: true`를 반환할 수 있다.

## 5. 주요 비즈니스 규칙

- 피드는 인증 사진이 업로드된 챌린지만 표시한다.
- 피드는 `challenge_photos.created_at` 기준 최신순으로 정렬한다.
- soft delete된 사진은 피드에 노출하지 않는다.
- 본인이 업로드한 사진도 피드 조회에는 포함될 수 있으나, 프론트엔드는 좋아요 버튼을 비활성화해야 한다.
- `liked_by_me`는 현재 사용자가 해당 사진을 이미 좋아요했는지 나타낸다.
- `like_count`는 soft delete되지 않은 사진에 연결된 좋아요 수를 기준으로 계산한다.
- 삭제는 실제 파일과 row를 제거하지 않고 soft delete로 처리한다.
- 삭제된 사진에는 좋아요 등록, 좋아요 사용자 목록 조회가 불가능하다.
- 삭제 후에도 이미 지급된 업로드 보상과 좋아요 보상은 회수하지 않는다.
- 삭제 권한은 `challenge_photos.user_id == current_user.id`인 경우에만 허용한다.

## 6. DB 영향 범위

- `challenge_photos`
  - 피드 조회 시 `is_deleted = false` 조건을 적용한다.
  - 삭제 시 `is_deleted = true`, `deleted_at = now()`로 갱신한다.
  - 현재 DB 요약에 soft delete 컬럼이 없다면 이 기능 구현 전에 `is_deleted`, `deleted_at` 컬럼과 migration이 필요하다.
- `challenges`
  - 피드 카드의 제목, 카테고리 조회를 위해 join한다.
- `users`
  - 작성자 표시용 `user_id`, `nickname`, `profile_image_url` 조회가 필요하다.
  - 현재 `docs/generated/db-schema.md` 기준 `nickname`, `profile_image_url`이 없다면 응답 계약에 맞춰 사용자 프로필 표시 정책을 별도 정해야 한다.
- `likes`
  - `like_count`, `liked_by_me` 계산에 사용한다.
- `token_transactions`
  - soft delete 시 변경하지 않는다.

## 7. Service 책임

- `routers/`는 query parameter 검증과 service 호출만 담당한다.
- 피드 조회 조건, pagination, like 집계, `liked_by_me` 계산은 service에서 처리한다.
- 파일 URL 변환은 `FileStorage.get_url()` 또는 storage service를 통해 수행한다.
- soft delete 소유권 검증은 service에서 수행한다.
- soft delete는 DB transaction으로 처리한다.
- 피드 조회 응답은 내부 `file_path` 대신 표시 가능한 `file_url`만 반환한다.

## 8. Error Cases

| Status | Code | 조건 |
| --- | --- | --- |
| `401 Unauthorized` | `UNAUTHORIZED` | 인증 쿠키가 없거나 유효하지 않음 |
| `403 Forbidden` | `PHOTO_NOT_OWNED` | 다른 사용자의 사진 삭제 시도 |
| `404 Not Found` | `PHOTO_NOT_FOUND` | 사진이 존재하지 않거나 삭제된 사진을 삭제 불가로 처리하는 정책 |
| `422 Unprocessable Entity` | `INVALID_PAGINATION` | `limit`, `cursor` 값이 유효하지 않음 |

## 9. Test Cases

- 업로드된 인증 사진 목록이 최신순으로 반환된다.
- `is_deleted = true`인 사진은 피드에 반환되지 않는다.
- 피드 item은 `like_count`와 `liked_by_me`를 포함한다.
- 현재 사용자가 좋아요한 사진은 `liked_by_me: true`로 반환된다.
- limit 기본값은 20이고 최대값은 50으로 제한된다.
- cursor가 있으면 다음 페이지를 안정적으로 조회한다.
- 본인 사진 삭제 시 `is_deleted`와 `deleted_at`이 설정된다.
- 다른 사용자의 사진 삭제 시 `403`을 반환한다.
- 삭제된 사진은 이후 피드 조회에서 제외된다.
- 삭제 후 기존 `token_transactions`와 `likes` row는 회수하거나 삭제하지 않는다.

## 10. Frontend 연동 참고사항

- `/challenges/feed` 화면 진입 시 `GET /api/challenges/feed`를 호출한다.
- 무한 스크롤 또는 더보기 UI는 `next_cursor`가 있을 때만 활성화한다.
- 본인 게시물에는 삭제 버튼을 노출할 수 있다.
- 삭제 성공 후 해당 item을 목록에서 제거한다.
- 본인 게시물의 좋아요 버튼은 비활성화한다.
- `liked_by_me`가 true이면 중복 좋아요 요청을 보내지 않는다.
- 이미지 렌더링에는 `file_url`만 사용한다.
