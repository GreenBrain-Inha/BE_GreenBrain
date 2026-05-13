# Contributing Guide

이 문서는 GreenBrain 백엔드 작업 시 지켜야 할 브랜치, PR, 개발 규칙을 정리한다.

## Branch Strategy

- `main`: 운영/배포 기준 브랜치.
- `dev`: 개발 통합 브랜치.
- `feature/*`: 개인 기능 작업 브랜치.
- `main` 직접 push 금지.
- `dev` 직접 push 금지.
- 모든 기능 작업은 `dev`에서 `feature/*` 브랜치를 생성해 진행한다.
- `feature/*` 브랜치는 자유롭게 push할 수 있다.
- 기능 완료 후 `feature/*` → `dev` Pull Request를 생성한다.
- 최소 1명 이상 리뷰 후 `dev`에 merge한다.
- 최종 검토 후 `dev` → `main` Pull Request를 생성한다.

## Current Backend Structure

```text
app/
├── main.py
├── db/
│   └── __init__.py
├── models/
│   └── __init__.py
├── routers/
│   ├── auth.py
│   ├── chat.py
│   ├── tokens.py
│   ├── challenges.py
│   └── feed.py
├── services/
│   ├── auth.py
│   ├── carbon.py
│   ├── chat.py
│   ├── challenge_gen.py
│   ├── reward.py
│   ├── daily_reset.py
│   └── storage.py
└── schemas/
    ├── auth.py
    └── common.py

alembic/
└── versions/
    └── 20260512_0001_create_core_tables.py

tests/
```

## Backend Responsibilities

- `app/main.py`: FastAPI 앱 생성, 공통 설정, 라우터 등록.
- `app/db/__init__.py`: SQLAlchemy `Base`, engine/session, FastAPI DB dependency.
- `app/models/__init__.py`: 현재 SQLAlchemy ORM 모델의 단일 진입점.
- `app/routers/`: HTTP 요청/응답, 입력 검증, service 호출만 담당한다.
- `app/services/`: 비즈니스 로직, 외부 API 호출, token/storage/reward 처리를 담당한다.
- `app/schemas/`: Pydantic 요청/응답 DTO와 공통 응답 모델을 둔다.
- `alembic/versions/`: DB schema 변경 이력을 둔다.
- `tests/`: API, service, DB 모델, migration 동작을 검증한다.

## Development Rules

- 새 API는 `router → schema → service → model/migration → test` 순서로 변경 범위를 명시한다.
- FastAPI router는 HTTP 요청/응답과 입력 검증만 담당한다.
- 비즈니스 로직은 `services/`에 둔다.
- DB 모델 변경은 반드시 Alembic migration과 `docs/generated/db-schema.md` 갱신을 함께 진행한다.
- 새 라우터를 추가하거나 구현할 때 `app/main.py` 라우터 등록을 확인한다.
- OpenAI, ecologits, Supabase Storage 호출은 반드시 service 계층에서 처리한다.
- `token_transactions`와 `daily_token_state` 업데이트는 같은 DB transaction에서 처리한다.
- 토큰 잔액은 음수가 되면 안 된다.
- 좋아요 보상 milestone은 중복 지급되면 안 된다.
- placeholder 파일은 실제 endpoint, service 함수, test가 있어야 구현 완료로 판단한다.
- 관련 없는 기능 추가나 리팩터링을 하지 않는다.
- 커밋 메시지는 conventional commits 형식을 따른다. 예: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Pull Request Checklist

- 변경 범위가 issue 또는 active exec plan과 일치한다.
- 새 API의 router, schema, service, model/migration, test 영향 범위를 설명했다.
- DB 모델 변경 시 Alembic migration과 `docs/generated/db-schema.md`를 함께 갱신했다.
- `app/main.py` 라우터 등록 누락이 없다.
- 외부 API, storage, token/reward 로직이 service 계층에 있다.
- 관련 테스트를 추가하거나 갱신했고, 실행 결과를 PR에 적었다.
