# 챌린지 인증 사진 업로드/파일 저장/업로드 보상 Spec

## 1. 목적

사용자가 수락한 챌린지를 인증 사진으로 완료하고, 파일을 저장하며, 업로드 보상을 지급하는 기능 계약을 정의한다. 이 문서는 인증 사진 업로드, Supabase Storage 파일 저장 정책, 업로드 보상만 다룬다.

## 2. 담당 Owner

- Primary owner: 김찬혁
- Reviewer: 장태환
- Reviewer 지정 사유: 업로드 보상은 `daily_token_state`와 `token_transactions`를 변경한다.

## 3. 관련 API

| Method | URL | 설명 |
| --- | --- | --- |
| `POST` | `/api/challenges/{id}/photo` | 챌린지 인증 사진 업로드 |

API는 JWT 인증된 사용자만 호출할 수 있다.

## 4. Request / Response

### POST /api/challenges/{id}/photo

#### Request

- Content-Type: `multipart/form-data`

| Field | Type | Required | 설명 |
| --- | --- | --- | --- |
| `file` | file | Yes | JPEG, PNG, WebP 이미지 |

#### Success Response

- Status: `201 Created`

```json
{
  "photo": {
    "id": "uuid",
    "challenge_id": "uuid",
    "file_url": "https://storage.example.com/challenge-photos/uuid.webp",
    "created_at": "2026-05-14T09:10:00Z"
  },
  "challenge": {
    "id": "uuid",
    "status": "completed",
    "completed_at": "2026-05-14T09:10:00Z"
  },
  "reward": {
    "type": "upload_reward",
    "reward_amount": 20,
    "tokens_remaining": 70
  }
}
```

기본 토큰 150을 이미 보유한 경우에도 업로드 보상은 지급되며, 보상으로 토큰 잔액이 150을 초과할 수 있다.

```json
{
  "photo": {
    "id": "uuid",
    "challenge_id": "uuid",
    "file_url": "https://storage.example.com/challenge-photos/uuid.webp",
    "created_at": "2026-05-14T09:10:00Z"
  },
  "challenge": {
    "id": "uuid",
    "status": "completed",
    "completed_at": "2026-05-14T09:10:00Z"
  },
  "reward": {
    "type": "upload_reward",
    "reward_amount": 20,
    "tokens_remaining": 170
  }
}
```

## 5. 주요 비즈니스 규칙

- 인증 사진은 `active` 상태의 본인 챌린지에만 업로드할 수 있다.
- 챌린지 하나에는 인증 사진 하나만 허용한다.
- 업로드 성공 시 `challenge_photos` row를 생성하고 챌린지를 `completed` 상태로 변경한다.
- 업로드 보상은 해당 인증 사진에 대해 1회만 지급한다.
- 업로드 기본 보상은 `+20` 토큰이다.
- 업로드 보상은 기본 토큰 150을 초과해 누적될 수 있다.
- KST 기준 daily state를 사용한다.
- 파일 형식은 JPEG, PNG, WebP만 허용한다.
- 원본 파일 크기는 최대 10MB까지 허용한다.
- 서버에서 이미지 후처리를 수행하며 최대 변 길이는 1280px로 제한하고 메타데이터는 제거한다.
- MVP 로컬 개발은 `LocalFileStorage`, 프로덕션 또는 Supabase 구성 환경은 `SupabaseStorage`를 사용하되, router는 저장소 구현을 직접 호출하지 않는다.
- 클라이언트에는 내부 저장 경로 또는 service role key를 노출하지 않는다.

## 6. DB 영향 범위

- `challenge_photos`
  - `challenge_id`, `user_id`, `file_path`, `upload_rewarded`, `created_at` 저장
  - `challenge_id` unique 제약으로 챌린지당 사진 1개를 보장한다.
- `challenges`
  - 업로드 성공 시 `status = completed`, `completed_at = now()`로 갱신
- `daily_token_state`
  - KST 기준 오늘 row를 조회 또는 lazy initialize
  - `tokens_remaining`, `upload_reward_given`, `total_reward_given`, `updated_at` 갱신
- `token_transactions`
  - 업로드 보상 이력 저장
  - `type = upload_reward`
  - `amount = 실제 지급액`
  - `source_type = photo`
  - `source_id = photo_id`
  - `milestone = null`

## 7. Service 책임

- `routers/`는 multipart 입력 검증과 service 호출만 담당한다.
- 챌린지 소유권, 상태, 중복 업로드 여부는 service에서 검증한다.
- 파일 검증, 이미지 리사이즈, 메타데이터 제거, 저장 key 생성은 service 계층에서 처리한다.
- 실제 파일 저장은 `services/storage.py`의 `FileStorage` 인터페이스를 통해 수행한다.
- Supabase Storage 연동 시 service role key와 bucket 정책은 서버 설정으로만 관리한다.
- DB 변경과 보상 지급은 하나의 transaction으로 처리한다.
- 파일 저장 성공 후 DB transaction이 실패하면 저장된 파일 정리 정책을 service에 둔다.
- 보상 계산은 `services/reward.py` 또는 보상 경계 service에서 처리한다.

## 8. Error Cases

| Status | Code | 조건 |
| --- | --- | --- |
| `401 Unauthorized` | `UNAUTHORIZED` | 인증 쿠키가 없거나 유효하지 않음 |
| `403 Forbidden` | `CHALLENGE_NOT_OWNED` | 다른 사용자의 챌린지에 업로드 |
| `404 Not Found` | `CHALLENGE_NOT_FOUND` | 챌린지가 존재하지 않음 |
| `409 Conflict` | `CHALLENGE_NOT_ACTIVE` | 챌린지가 `active` 상태가 아님 |
| `409 Conflict` | `PHOTO_ALREADY_UPLOADED` | 해당 챌린지에 이미 사진이 있음 |
| `413 Payload Too Large` | `FILE_TOO_LARGE` | 파일 크기가 10MB 초과 |
| `415 Unsupported Media Type` | `UNSUPPORTED_IMAGE_TYPE` | JPEG, PNG, WebP가 아닌 파일 |
| `422 Unprocessable Entity` | `INVALID_IMAGE` | 이미지 파싱 또는 후처리 실패 |
| `502 Bad Gateway` | `STORAGE_WRITE_FAILED` | 파일 저장 실패 |

## 9. Test Cases

- `active` 상태의 본인 챌린지에 정상 이미지를 업로드하면 사진 row가 생성된다.
- 업로드 성공 시 챌린지 상태가 `completed`로 변경되고 `completed_at`이 설정된다.
- 업로드 성공 시 `upload_reward` token transaction이 생성된다.
- 토큰 잔액이 140이면 실제 지급액은 10이고 잔액은 150이 된다.
- 토큰 잔액이 150이면 실제 지급액은 0이고 사진 업로드는 성공한다.
- 이미 사진이 있는 챌린지에 다시 업로드하면 `409 PHOTO_ALREADY_UPLOADED`를 반환한다.
- 다른 사용자의 챌린지에 업로드하면 `403`을 반환한다.
- `pending_acceptance` 또는 `completed` 챌린지 업로드는 `409`를 반환한다.
- 10MB 초과 파일은 `413`을 반환한다.
- 허용되지 않은 확장자 또는 MIME type은 `415`를 반환한다.
- 깨진 이미지 파일은 `422`를 반환한다.
- 저장소 실패 시 DB에 사진 row와 보상 transaction이 남지 않는다.

## 10. Frontend 연동 참고사항

- `/challenges` 화면의 `active` 챌린지에서만 업로드 UI를 활성화한다.
- 업로드 전 클라이언트에서도 파일 크기와 형식을 1차 검증하되, 서버 검증 결과를 최종 기준으로 사용한다.
- 업로드 성공 후 토큰 잔액과 챌린지 상태를 응답값으로 갱신한다.
- `reward.reward_amount`가 0이어도 업로드 실패로 표시하지 않는다.
- 파일 업로드 중 중복 클릭을 막기 위해 submit 버튼을 비활성화한다.
- 응답의 `file_url`만 이미지 표시용으로 사용하고 `file_path` 또는 저장소 내부 key는 노출하지 않는다.

## Storage backend policy

- `STORAGE_BACKEND=local` keeps using `LocalFileStorage`.
- `STORAGE_BACKEND=supabase` uses `SupabaseStorage`.
- Supabase uploads use bucket `greenbrain-uploads`.
- Stored challenge photo object keys are `challenge-photos/{photo_id}.webp`; the bucket name is not duplicated in the object key.
- Supabase public URLs support both base URL forms:
  `{SUPABASE_STORAGE_PUBLIC_BASE_URL}/{SUPABASE_STORAGE_BUCKET}/{key}` when the base URL excludes the bucket,
  or `{SUPABASE_STORAGE_PUBLIC_BASE_URL}/{key}` when the base URL already includes the bucket.
- `SUPABASE_STORAGE_PUBLIC_BASE_URL` may be either `https://<project-ref>.supabase.co/storage/v1/object/public`
  or `https://<project-ref>.supabase.co/storage/v1/object/public/greenbrain-uploads`.
- The API response shape does not change; clients continue to read `photo.file_url`.
