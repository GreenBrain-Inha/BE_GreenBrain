### **Architecture: GreenBrain (MVP)

작성일: 2026-05-04 | 연계 문서: [PRD](references/PRD.md), [ADR](ADR.md)**

---

## 1. 디렉토리 구조

```text
.
├── app/                         # FastAPI 백엔드 애플리케이션
│   ├── main.py                  # FastAPI 앱 초기화, 라우터 등록, CORS 설정
│   ├── core/                    # 앱 전역 설정 및 보안 유틸리티
│   │   ├── config.py            # 환경변수 기반 Settings (DATABASE_URL, JWT_SECRET_KEY 등)
│   │   └── security.py          # JWT/쿠키 보안 상수 및 헬퍼
│   ├── routers/                 # HTTP 엔드포인트. 입력 검증 후 service 호출만 담당
│   │   ├── auth.py              # /api/auth/*
│   │   ├── chat.py              # /api/chat/*
│   │   ├── users.py             # /api/users/*
│   │   ├── tokens.py            # /api/tokens/*
│   │   ├── challenges.py        # /api/challenges/*
│   │   └── feed.py              # /api/feed/*
│   ├── services/                # 비즈니스 로직. 라우터와 DB 사이의 유일한 로직 레이어
│   │   ├── auth.py              # 회원가입, 로그인, JWT 발급
│   │   ├── carbon.py            # ecologits 래퍼. 실패 시 None 반환
│   │   ├── chat.py              # OpenAI 응답 + 탄소 계산 + 토큰 차감 플로우 조합
│   │   ├── chat_session.py      # 채팅 세션 CRUD
│   │   ├── challenge_gen.py     # 챌린지 생성 (프로필 + 이력 컨텍스트)
│   │   ├── token_account.py     # 토큰 사용 / 사진, 좋아요 보상 계산. 일일 상한 로직 포함
│   │   ├── daily_reset.py       # KST 자정 기준 lazy initialization
│   │   └── storage.py           # FileStorage 인터페이스 + Local Storage 구현, Supabase Storage 확장 예정
│   ├── models/                  # SQLAlchemy ORM 모델. DB 스키마와 1:1 대응
│   │   ├── _mixins.py           # 공유 컬럼 헬퍼 (uuid_pk, timestamp_column)
│   │   ├── user.py              # User, UserProfile
│   │   ├── chat.py              # ChatSession, Message
│   │   ├── token.py             # DailyTokenState, TokenTransaction
│   │   └── challenge.py         # Challenge, ChallengePhoto, Like
│   ├── schemas/                 # Pydantic API 요청/응답 DTO
│   │   ├── auth.py              # 회원가입/로그인 요청·응답
│   │   ├── chat.py              # 채팅 메시지 요청·응답
│   │   ├── chat_session.py      # 채팅 세션 요청·응답
│   │   └── common.py            # ApiError, Errors, error_response
│   └── db/                      # DB 엔진 생성, 세션 관리
├── alembic/                     # Alembic 마이그레이션
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/                       # pytest. services/ 단위 테스트 중심
├── docs/                        # 아키텍처, 스펙, 참조 문서
│   ├── ARCHITECTURE.md
│   ├── ADR.md
│   ├── specs/                   # 기능별 상세 SPEC
│   ├── exec-plans/              # 이슈 단위 실행 계획
│   │   ├── active/
│   │   └── completed/
│   ├── generated/               # 코드에서 동기화되는 문서 (db-schema.md 등)
│   └── references/              # PRD, MVP 범위 등 참조 문서
├── .agents/                     # 공통 workflow, agent, skill 정의
│   ├── agents/
│   ├── skills/
│   └── workflows/
├── .github/                     # GitHub 이슈/PR 템플릿
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── .pre-commit-config.yml       # 포맷/린트/실수 방지 pre-commit hook 설정
├── alembic.ini
├── CLAUDE.md                    # Claude 작업 지침
└── AGENTS.md                    # 공통 agent 작업 지침
```

---

## 2. System Overview

GreenBrain은 AI 챗봇 사용량을 탄소 토큰으로 환산하고, 토큰 소진 시 실생활 챌린지 수행으로 토큰을 회복하는 반응형 웹 서비스다.

```
[Browser: Next.js]
        ↕ HTTP/REST (JSON)
[FastAPI]
  ├── OpenAI API          (GPT-4o mini 채팅 응답)
  ├── ecologits           (메시지별 gCO₂eq 계산)
  └── Supabase Storage    (챌린지 인증 사진 저장)
        ↕ SQL
[Supabase PostgreSQL]
```

### 핵심 아키텍처 원칙

- LLM 호출, ecologits 호출, 토큰 차감/회복 로직은 FastAPI에서만 처리한다.
- Next.js는 API 키를 보유하지 않으며 FastAPI를 통해서만 백엔드에 접근한다.
- Supabase는 PostgreSQL 데이터 영속성과 인증 사진 저장소 용도로 사용한다.
- 사용자 인증은 FastAPI JWT + bcrypt 기반으로 처리한다.
- 모든 토큰 변화는 `daily_token_state`에 최종 잔액으로 반영하고, `token_transactions`에 거래 이력으로 기록한다.
- `like_reward_log`는 별도 테이블로 두지 않고, 좋아요 보상 이력은 `token_transactions`에 통합한다.

---

## 3. Tech Stack

| 레이어 | 기술 | 역할 |
| --- | --- | --- |
| Frontend | Next.js + TypeScript + shadcn + Tailwind CSS | 반응형 웹 UI, 라우팅 |
| Backend | FastAPI (Python) | 인증, 비즈니스 로직, 외부 API 오케스트레이션 |
| Database | Supabase PostgreSQL | 데이터 영속성 |
| Auth | FastAPI JWT + bcrypt | 회원가입, 로그인, 인증 쿠키 관리 |
| LLM | OpenAI GPT-4o mini | AI 채팅 응답 생성 |
| 탄소 계산 | ecologits | 메시지별 gCO₂eq 측정 |
| 파일 저장 | Local FS(로컬 개발) → Supabase Storage(배포) | 챌린지 인증 사진 저장 |

---

## 4. Data Model

### ERD 개요

```
users ──────────── user_profiles
  │                 (1:1)
  ├── chat_sessions
  │   (1:N)
  │     └── messages
  │           (1:N)
  ├── daily_token_state
  │   (1:N, 날짜별)
  ├── token_transactions
  │   (1:N)
  └── challenges
        (1:N)
          └── challenge_photos
                (1:0..1)
                  └── likes
                        (1:N)
```

---

### users

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 사용자 ID |
| email | VARCHAR UNIQUE | 이메일 |
| password_hash | VARCHAR | bcrypt 해시 비밀번호 |
| nickname | VARCHAR NULL | 서비스 내 표시 이름 |
| profile_image_url | VARCHAR NULL | 프로필 이미지 URL |
| created_at | TIMESTAMPTZ | 생성 시각 |
| updated_at | TIMESTAMPTZ | 수정 시각 |

---

### user_profiles

온보딩에서 수집한 생활 습관 프로필이다.

챌린지 생성 시 개인화 컨텍스트로 사용되며, 사용자는 마이페이지에서 생활습관 프로필을 조회하거나 수정할 수 있다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| user_id | UUID PK, FK users.id | 사용자 ID |
| transport_mode | VARCHAR | 교통수단: car / transit / walk 등 |
| diet_type | VARCHAR | 식단 유형: omnivore / vegetarian 등 |
| housing_type | VARCHAR | 주거 형태: apartment / house 등 |

---

### chat_sessions

사용자별 채팅 세션을 기록한다. 메시지는 항상 하나의 세션에 속한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 채팅 세션 ID |
| user_id | UUID FK users.id | 사용자 ID |
| title | VARCHAR NULL | 세션 제목. 최초 메시지 기반 자동 생성 또는 사용자 수정 |
| created_at | TIMESTAMPTZ | 생성 시각 |
| updated_at | TIMESTAMPTZ | 수정 시각 |

---

### messages

채팅 메시지와 메시지별 탄소 배출량을 기록한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 메시지 ID |
| user_id | UUID FK users.id | 사용자 ID |
| session_id | UUID FK chat_sessions.id | 채팅 세션 ID |
| role | VARCHAR | user / assistant |
| content | TEXT | 메시지 내용 |
| carbon_gco2eq | FLOAT NULL | 해당 메시지의 탄소 배출량. ecologits 실패 시 null |
| created_at | TIMESTAMPTZ | 생성 시각 |

---

### daily_token_state

사용자별 날짜별 토큰 상태를 저장한다. KST 기준 하루에 1행을 가진다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| user_id | UUID FK users.id | 사용자 ID |
| date | DATE | KST 기준 날짜 |
| tokens_remaining | FLOAT | 남은 토큰. 기본값 150.0 |
| upload_reward_given | FLOAT | 오늘 사진 업로드 보상으로 지급된 토큰 합계 |
| like_reward_given | FLOAT | 오늘 좋아요 보상으로 지급된 토큰 합계. 상한 60 |
| total_reward_given | FLOAT | 오늘 전체 회복 토큰 합계 |
| challenge_count | INT | 오늘 생성한 챌린지 수 |
| updated_at | TIMESTAMPTZ | 수정 시각 |

제약조건:

```
PRIMARY KEY (user_id, date)
```

토큰 정책:

- KST 기준 오늘 날짜의 행이 없으면 기본값 150.0으로 생성한다.
- `tokens_remaining`은 0 미만이 될 수 없다.
- 보상 지급 후에도 `tokens_remaining`은 기본 토큰 한도인 150.0을 초과할 수 없다.
- 실제 보상 지급량은 `min(보상 예정량, 150.0 - 현재 tokens_remaining)`으로 계산한다.

---

### token_transactions

토큰 차감, 사진 보상, 좋아요 보상, 일일 초기화 등 모든 토큰 변화 이력을 기록한다.

`like_reward_log`는 별도 테이블로 두지 않고, `token_transactions`의 `type = 'like_reward'`, `source_type = 'photo'`, `source_id = photo_id`, `milestone = 3/6/9...` 형태로 통합 관리한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 토큰 거래 ID |
| user_id | UUID FK users.id | 토큰이 변한 사용자 |
| daily_state_date | DATE | KST 기준 날짜. `daily_token_state.date`와 연결 |
| type | VARCHAR | chat_usage / upload_reward / like_reward / daily_reset |
| amount | FLOAT | 차감은 음수, 회복은 양수 |
| balance_after | FLOAT | 반영 후 토큰 잔액 |
| source_type | VARCHAR NULL | message / photo / challenge / daily_reset |
| source_id | UUID NULL | 원인이 된 리소스 ID |
| milestone | INT NULL | 좋아요 보상 구간. 3, 6, 9 등 |
| memo | TEXT NULL | 보조 설명 |
| created_at | TIMESTAMPTZ | 생성 시각 |

주요 규칙:

- `type = chat_usage`이면 `amount`는 음수다.
- `type = upload_reward`, `like_reward`, `daily_reset`이면 `amount`는 양수 또는 0이다.
- 좋아요 보상은 `milestone` 단위로 중복 지급되지 않아야 한다.
- 좋아요 보상 중복 방지를 위해 PostgreSQL partial unique index를 사용한다.

```sql
CREATE UNIQUE INDEX uq_token_transactions_like_reward_milestone
ON token_transactions (source_type, source_id, milestone)
WHERE type = 'like_reward';
```

예시:

| type | amount | source_type | source_id | milestone | 의미 |
| --- | --- | --- | --- | --- | --- |
| chat_usage | -0.42 | message | message_id | null | 채팅으로 0.42 토큰 차감 |
| upload_reward | +20 | photo | photo_id | null | 사진 업로드 보상 지급 |
| like_reward | +20 | photo | photo_id | 3 | 좋아요 3개 보상 지급 |
| like_reward | +20 | photo | photo_id | 6 | 좋아요 6개 보상 지급 |
| daily_reset | +150 | daily_reset | 2026-05-04 | null | 일일 토큰 초기화 |

---

### challenges

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 챌린지 ID |
| user_id | UUID FK users.id | 챌린지 소유자 |
| category | VARCHAR | transport / diet / energy |
| title | VARCHAR | 챌린지 제목 |
| description | TEXT | 상세 설명 |
| difficulty | INT | 1~3. 누적 완료 횟수 기반 |
| status | VARCHAR | pending_acceptance / active / completed |
| created_at | TIMESTAMPTZ | 생성 시각 |
| completed_at | TIMESTAMPTZ NULL | 완료 시각 |

상태 정책:

- 챌린지는 생성 직후 `pending_acceptance` 상태가 된다.
- 사용자가 수락하면 `active` 상태가 된다.
- 사진 업로드가 완료되면 `completed` 상태가 된다.
- 사용자는 동시에 하나의 `pending_acceptance` 또는 `active` 챌린지만 가질 수 있다.

---

### challenge_photos

챌린지 인증 사진을 저장한다. 챌린지당 1장의 사진만 허용한다.

피드 삭제는 실제 row를 삭제하지 않고 `is_deleted = true`로 처리한다.

이미 지급된 업로드 보상과 좋아요 보상은 삭제 시 회수하지 않는다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 사진 ID |
| challenge_id | UUID FK challenges.id UNIQUE | 챌린지 ID. 챌린지당 1장 |
| user_id | UUID FK users.id | 업로더 ID |
| file_path | VARCHAR | Supabase Storage 경로 또는 로컬 개발 저장 경로 |
| upload_rewarded | BOOL | 업로드 보상 지급 여부 |
| is_deleted | BOOL | 피드 삭제 여부. 기본값 false |
| deleted_at | TIMESTAMPTZ NULL | 삭제 시각 |
| created_at | TIMESTAMPTZ | 생성 시각 |

정책:

- 피드 삭제는 사진 업로더 본인만 가능하다.
- 삭제는 soft delete로 처리한다.
- 삭제된 사진은 인증 피드에 노출하지 않는다.
- 삭제된 사진에는 추가 좋아요를 누를 수 없다.
- 삭제되어도 이미 지급된 업로드 보상과 좋아요 보상은 회수하지 않는다.

---

### likes

사진에 대한 좋아요를 기록한다.

좋아요를 누른 사용자 목록을 보여주기 위해 `liker_user_id`를 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | UUID PK | 좋아요 ID |
| photo_id | UUID FK challenge_photos.id | 사진 ID |
| liker_user_id | UUID FK users.id | 좋아요를 누른 사용자 |
| created_at | TIMESTAMPTZ | 생성 시각 |

제약조건:

```
UNIQUE (photo_id, liker_user_id)
```

정책:

- 동일 사용자는 같은 사진에 중복 좋아요를 누를 수 없다.
- 본인 사진에는 좋아요를 누를 수 없다.
- 삭제된 사진에는 좋아요를 누를 수 없다.
- 계정 생성 후 24시간 이내 신규 계정은 좋아요를 누를 수 없다.
- 좋아요 사용자 목록에는 이메일을 노출하지 않는다.

---

## 5. API Surface

상세 요청/응답 스펙은 각 feature spec을 참조한다.

| 그룹 | 엔드포인트 | 설명 |
| --- | --- | --- |
| Auth | `POST /api/auth/signup` | 회원가입 |
| Auth | `POST /api/auth/login` | 로그인, JWT 쿠키 발급 |
| Auth | `POST /api/auth/logout` | 로그아웃, 쿠키 삭제 |
| Users | `GET /api/users/me` | 현재 사용자 정보 조회 |
| Users | `PATCH /api/users/me` | 닉네임 등 사용자 기본 프로필 수정 |
| Users | `GET /api/users/profile` | 현재 사용자 생활습관 프로필 조회 |
| Users | `PATCH /api/users/profile` | 현재 사용자 생활습관 프로필 수정 |
| Users | `POST /api/users/onboarding` | 생활 습관 프로필 저장 |
| Chat | `POST /api/chat/sessions` | 채팅 세션 생성 |
| Chat | `GET /api/chat/sessions` | 채팅 세션 목록 조회 |
| Chat | `PATCH /api/chat/sessions/{session_id}` | 채팅 세션 제목 수정 |
| Chat | `DELETE /api/chat/sessions/{session_id}` | 채팅 세션 삭제 |
| Chat | `POST /api/chat/sessions/{session_id}/messages` | 메시지 전송, 응답 + 탄소량 + 토큰 잔여량 반환 |
| Chat | `GET /api/chat/sessions/{session_id}/messages` | 세션별 메시지 목록 조회 |
| Tokens | `GET /api/tokens/today` | 오늘의 토큰 상태 조회 |
| Challenges | `GET /api/challenges/current` | 현재 활성 챌린지 조회 |
| Challenges | `POST /api/challenges/generate` | 챌린지 자동 생성 |
| Challenges | `POST /api/challenges/{id}/accept` | 챌린지 수락 |
| Challenges | `POST /api/challenges/{id}/photo` | 인증 사진 업로드 |
| Challenges | `GET /api/challenges/feed` | 인증 피드 목록 최신순 조회 |
| Challenges | `POST /api/challenge-photos/{photo_id}/like` | 인증 사진 좋아요 |
| Challenges | `DELETE /api/challenge-photos/{photo_id}` | 본인 인증 피드 게시물 삭제 |
| Challenges | `GET /api/challenge-photos/{photo_id}/likes` | 해당 사진에 좋아요를 누른 사용자 목록 조회 |

---

## 6. Core Data Flows

### 6.1 채팅 → 탄소 토큰 차감

```
사용자 메시지 전송
  → Next.js: POST /api/chat/sessions/{session_id}/messages
  → FastAPI:
      1. chat_sessions 소유권 확인
      2. 오늘의 daily_token_state 조회 또는 생성
         └─ KST 기준 오늘 날짜 행이 없으면 tokens_remaining = 150.0으로 생성
      3. tokens_remaining > 0인지 확인
         └─ 0이면 채팅 요청 차단
      4. OpenAI 호출 → 응답 텍스트 생성
      5. ecologits 호출 → gCO₂eq 계산
         └─ 실패 시: carbon_gco2eq = null, 차감 건너뜀
      6. DB transaction 안에서 daily_token_state 행을 row-level lock으로 잠금
      7. tokens_remaining -= gCO₂eq
         └─ 0 이하가 되면 0으로 고정하고 exhausted = true
      8. messages 저장
         └─ user 메시지와 assistant 메시지 모두 session_id 연결
      9. token_transactions 저장
         └─ type = chat_usage
         └─ amount = -gCO₂eq
         └─ balance_after = 차감 후 잔액
         └─ source_type = message
         └─ source_id = assistant message_id
      10. 응답: { response, carbon_gco2eq, tokens_remaining, exhausted, session_title }
  → Next.js:
      - 응답 하단에 메시지별 탄소량 표시
      - 토큰 바 업데이트
      - exhausted == true → /challenges 이동
```

---

### 6.2 토큰 소진 → 챌린지 생성

```
토큰 소진 감지 (exhausted == true)
  → Next.js: POST /api/challenges/generate
  → FastAPI:
      1. 오늘의 daily_token_state 조회 또는 생성
      2. 진행 중 챌린지 존재 여부 확인
         └─ pending_acceptance 또는 active 상태 챌린지가 있으면 기존 챌린지 반환
      3. challenge_count_today >= 3이면 생성 불가 반환
      4. user_profiles + challenge 이력 조회
      5. LLM으로 챌린지 생성
         └─ category, title, description, difficulty 생성
      6. challenges 테이블 저장
         └─ status = pending_acceptance
      7. challenge_count += 1
      8. 챌린지 반환

사용자 수락
  → Next.js: POST /api/challenges/{id}/accept
  → FastAPI:
      1. 챌린지 소유자 확인
      2. pending_acceptance 상태인지 확인
      3. status = active로 변경
```

---

### 6.3 사진 업로드 → 즉시 토큰 회복

```
사용자 사진 업로드
  → Next.js: POST /api/challenges/{id}/photo (multipart/form-data)
  → FastAPI:
      1. 챌린지 소유자 확인
      2. active 상태의 챌린지인지 확인
      3. 기존 사진이 없는지 확인
      4. 파일 유효성 검사
         └─ JPEG / PNG / WebP
         └─ 최대 10MB
      5. 이미지 리사이즈
         └─ 최대 1280px, 비율 유지
      6. 파일 저장
         └─ 로컬 개발: Local FS
         └─ 배포 환경: Supabase Storage
      7. challenge_photos 저장
      8. challenge status = completed
      9. daily_token_state 행을 row-level lock으로 잠금
      10. 업로드 보상 계산
          └─ 기본 +20 토큰
          └─ 실제 지급량 = min(20, 150.0 - 현재 tokens_remaining)
      11. tokens_remaining 업데이트
      12. daily_token_state.upload_reward_given, total_reward_given 업데이트
      13. token_transactions 저장
          └─ type = upload_reward
          └─ amount = 실제 지급된 토큰
          └─ balance_after = 지급 후 잔액
          └─ source_type = photo
          └─ source_id = photo_id
      14. upload_rewarded = true
      15. 응답:
          {
            "photo": {
              "id": "photo_id",
              "challenge_id": "challenge_id",
              "file_url": "https://...",
              "created_at": "2026-05-14T09:10:00Z"
            },
            "challenge": {
              "id": "challenge_id",
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

---

### 6.4 좋아요 → 단계별 토큰 회복

```
사용자가 피드 사진에 좋아요
  → Next.js: POST /api/challenge-photos/{photo_id}/like
  → FastAPI:
      1. 사진 존재 여부 확인
      2. photo.is_deleted = false인지 확인
         └─ 삭제된 사진이면 404 Not Found
      3. 어뷰징 검사
         └─ 본인 사진 좋아요 불가
         └─ 동일 사진 중복 좋아요 불가
         └─ 계정 생성 24시간 이내 좋아요 불가
      4. likes 테이블에 insert
      5. 해당 photo의 총 좋아요 수 계산
      6. 새로운 3의 배수 milestone 도달 여부 확인
         └─ 예: 3, 6, 9 ...
      7. milestone 도달이 아니면 보상 없이 종료
      8. daily_token_state 행을 row-level lock으로 잠금
      9. token_transactions에서 기존 like_reward milestone 지급 여부 확인
         └─ source_type = photo
         └─ source_id = photo_id
         └─ milestone = 현재 milestone
      10. 이미 지급된 milestone이면 보상 없이 종료
      11. 업로더의 like_reward_given_today 확인
          └─ 60 이상이면 보상 없음
          └─ 60 미만이면 min(20, 60 - like_reward_given_today, 150.0 - 현재 tokens_remaining) 지급
      12. tokens_remaining 업데이트
      13. daily_token_state.like_reward_given, total_reward_given 업데이트
      14. token_transactions 저장
          └─ type = like_reward
          └─ amount = 실제 지급된 토큰
          └─ balance_after = 지급 후 잔액
          └─ source_type = photo
          └─ source_id = photo_id
          └─ milestone = 현재 milestone
      15. 응답:
          {
            liked: true,
            like_count,
            reward_given,
            reward_amount,
            tokens_remaining
          }
```

중복 보상 방지:

```
좋아요 보상 지급은 DB transaction 안에서 처리한다.
type = like_reward인 token_transactions에 대해
(source_type, source_id, milestone) 조합이 중복되지 않도록 partial unique index를 둔다.
```

---

### 6.5 프로필 정보 및 생활습관 프로필 수정

```
사용자 프로필 화면 진입
  → Next.js: GET /api/users/me
  → FastAPI:
      1. JWT에서 current_user 확인
      2. users 테이블에서 기본 프로필 조회
      3. 응답: { id, email, nickname, profile_image_url }

사용자 기본 프로필 수정
  → Next.js: PATCH /api/users/me
  → FastAPI:
      1. JWT에서 current_user 확인
      2. nickname, profile_image_url 등 입력값 검증
      3. users 테이블 업데이트
      4. updated_at 갱신
      5. 응답: 수정된 기본 프로필 반환

생활습관 프로필 조회
  → Next.js: GET /api/users/profile
  → FastAPI:
      1. JWT에서 current_user 확인
      2. user_profiles 조회
      3. 응답: { transport_mode, diet_type, housing_type, updated_at }

생활습관 프로필 수정
  → Next.js: PATCH /api/users/profile
  → FastAPI:
      1. JWT에서 current_user 확인
      2. 입력값 검증
      3. user_profiles 업데이트
      4. updated_at 갱신
      5. 응답: 수정된 생활습관 프로필 반환
```

---

### 6.6 챌린지 피드 삭제

```
사용자가 본인 인증 피드 게시물 삭제
  → Next.js: DELETE /api/challenge-photos/{photo_id}
  → FastAPI:
      1. JWT에서 current_user 확인
      2. challenge_photos 조회
      3. photo.user_id == current_user.id인지 확인
         └─ 아니면 403 Forbidden
      4. 이미 삭제된 게시물인지 확인
         └─ 이미 삭제된 경우 deleted: true 반환 또는 404 처리
      5. is_deleted = true
      6. deleted_at = now()
      7. 응답: { deleted: true }

피드 조회 시
  → Next.js: GET /api/challenges/feed
  → FastAPI:
      1. is_deleted = false인 사진만 조회
      2. 최신순으로 반환
```

정책:

- 삭제는 soft delete로 처리한다.
- 삭제된 사진은 피드에 노출하지 않는다.
- 삭제된 사진에는 추가 좋아요를 누를 수 없다.
- 삭제되어도 이미 지급된 업로드 보상과 좋아요 보상은 회수하지 않는다.

---

### 6.7 좋아요 사용자 목록 조회

```
사용자가 피드에서 좋아요 사용자 목록 확인
  → Next.js: GET /api/challenge-photos/{photo_id}/likes
  → FastAPI:
      1. JWT에서 current_user 확인
      2. challenge_photos 조회
      3. photo.is_deleted = false인지 확인
         └─ 삭제된 사진이면 404 Not Found
      4. likes와 users를 join하여 좋아요 누른 사용자 목록 조회
      5. 응답:
         [
           {
             user_id,
             nickname,
             profile_image_url,
             liked_at
           }
         ]
```

정책:

- 좋아요 사용자 목록에는 이메일을 노출하지 않는다.
- 응답에는 `user_id`, `nickname`, `profile_image_url`, `liked_at`만 포함한다.
- 삭제된 사진의 좋아요 사용자 목록은 조회할 수 없다.

---

## 7. Auth & Security

- JWT는 HttpOnly + Secure 쿠키에 저장한다.
- JWT 만료 시간은 7일로 설정한다.
- 비밀번호는 bcrypt로 해시 저장한다.
- 비밀번호는 최소 8자 이상이며, 대소문자와 숫자를 포함해야 한다.
- 로그인 실패 5회 초과 시 15분 동안 잠금 처리한다.
- API 키는 클라이언트에 노출하지 않고 서버 환경변수로만 관리한다.
- 본인 사진 좋아요는 차단한다.
- 동일 사진 중복 좋아요는 `UNIQUE(photo_id, liker_user_id)` 제약조건으로 차단한다.
- 계정 생성 후 24시간 이내 신규 계정은 좋아요 버튼을 비활성화한다.
- 피드 게시물 삭제는 `challenge_photos.user_id == current_user.id`인 경우에만 허용한다.
- 삭제된 피드 게시물은 피드 조회, 좋아요, 좋아요 사용자 목록 조회 대상에서 제외한다.
- 좋아요 사용자 목록에는 이메일을 노출하지 않는다.
- 좋아요 사용자 목록에는 `user_id`, `nickname`, `profile_image_url`, `liked_at`만 반환한다.

### 쿠키와 CORS 주의사항

프론트엔드와 백엔드가 서로 다른 도메인에 배포될 경우 HttpOnly 쿠키 전달을 위해 다음 설정이 필요하다.

- FastAPI CORS에서 `allow_credentials=True` 설정
- `allowed_origins`에 프론트엔드 배포 도메인 명시
- 서로 다른 도메인 간 쿠키 사용 시 `SameSite=None; Secure` 검토
- 같은 도메인 또는 프록시 구조를 사용할 경우 `SameSite=Strict` 또는 `Lax` 사용 가능

---

## 8. Infrastructure

### 파일 저장

로컬 개발과 배포 환경의 저장소 차이를 줄이기 위해 FastAPI 내부에 스토리지 추상화 인터페이스를 둔다.

```python
class FileStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...
    def get_url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...
```

- 로컬 개발: `LocalFileStorage` — 서버 로컬 디렉토리에 저장
- 배포 환경: `SupabaseStorage` — Supabase Storage 버킷에 저장
- 클라이언트에는 실제 저장 경로가 아니라 접근 가능한 public URL 또는 signed URL을 반환한다.

Storage backend selection:

- `STORAGE_BACKEND=local` selects `LocalFileStorage`.
- `STORAGE_BACKEND=supabase` selects `SupabaseStorage`.
- Supabase uses bucket `challenge-photos`.
- Challenge photo object keys are `{photo_id}.webp`.
- Supabase public URLs are `{SUPABASE_STORAGE_PUBLIC_BASE_URL}/{SUPABASE_STORAGE_BUCKET}/{key}`.
- `SUPABASE_STORAGE_PUBLIC_BASE_URL` excludes the bucket name, for example `https://<project-ref>.supabase.co/storage/v1/object/public`.

---

### 일일 토큰 초기화

KST 자정 기준으로 `daily_token_state`를 신규 행으로 생성한다.

요청 시점에 오늘 날짜 행이 없으면 FastAPI가 기본값 150 토큰으로 생성한다. 이 방식은 별도 크론 잡 없이 요청 시점에 초기화하는 lazy initialization 방식이다.

초기화 시 다음 작업을 수행한다.

```
1. daily_token_state에 오늘 날짜 행이 없으면 생성
2. tokens_remaining = 150.0 설정
3. upload_reward_given = 0 설정
4. like_reward_given = 0 설정
5. total_reward_given = 0 설정
6. challenge_count = 0 설정
```

필요 시 `token_transactions`에 `type = daily_reset` 기록을 남긴다.

---

### 이미지 처리

업로드 직후 FastAPI에서 Pillow로 이미지를 처리한다.

- 허용 포맷: JPEG, PNG, WebP
- 최대 파일 크기: 10MB
- 최대 이미지 크기: 1280px
- 원본 비율 유지
- 파일명은 UUID 기반으로 생성
- 클라이언트에는 실제 서버 경로가 아닌 접근 가능한 URL만 반환한다.
