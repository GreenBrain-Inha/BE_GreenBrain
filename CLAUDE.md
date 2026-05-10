# GreenBrain Claude 작업 지침

## 참고 문서

- 제품 요구사항: `docs/PRD.md`
- 아키텍처: `docs/ARCHITECTURE.md`
- 설계 결정: `docs/ADR.md`
- Harness 워크플로우: `.claude/commands/harness.md`
- 상세 기능 SPEC: `specs/ `

## 기술 스택

- 프론트엔드: Next.js, TypeScript, shadcn, Tailwind CSS
- 백엔드: FastAPI, Python 3.11+
- 데이터베이스: Supabase / PostgreSQL, SQLAlchemy ORM, Alembic
- AI: OpenAI GPT-4o mini
- 탄소 계산: ecologits
- 파일 저장: MVP는 로컬 파일시스템, 프로덕션은 S3 호환 스토리지

## 아키텍처 규칙

- CRITICAL: OpenAI와 ecologits 호출은 `services/`에서만 처리하고 `routers/`에서 직접 호출하지 말 것.
- CRITICAL: 토큰 차감과 보상 계산은 `services/reward.py`, `services/daily_reset.py` 경계 안에서만 처리할 것.
- CRITICAL: 파일 저장은 `services/storage.py`의 `FileStorage` 인터페이스를 통해서만 처리할 것.
- CRITICAL: 클라이언트 컴포넌트에서 OpenAI, ecologits, Supabase service role key 등 외부 API/비밀 키를 직접 호출하지 말 것.
- `routers/`는 입력 검증 후 service 호출만 담당하고 비즈니스 로직을 두지 말 것.
- API 요청/응답은 `schemas/`의 Pydantic 스키마를 사용할 것.
- DB 모델 변경 시 Alembic 마이그레이션을 함께 작성할 것.

## 개발 프로세스

- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것. (TDD)
- 변경 범위는 이슈 또는 harness step에 맞추고 관련 없는 기능을 추가하지 말 것.
- 커밋 메시지는 conventional commits 형식을 따를 것. 예: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

## 명령어

```bash
# 프론트엔드 개발 서버 실행
npm run dev

# 프론트엔드 프로덕션 빌드
npm run build

# 프론트엔드 린트 검사
npm run lint

# 프론트엔드 테스트 실행
npm run test

# FastAPI 백엔드 개발 서버 실행
python3 -m uvicorn app.main:app --reload

# Python 테스트 실행
python3 -m pytest
```
