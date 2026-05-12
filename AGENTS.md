# GreenBrain Agent Instructions

이 파일은 모든 LLM/agent가 먼저 읽는 공통 진입점이다. 세부 workflow, agent, skill 문서는 `.agents/` 아래에 둔다.

## 필수 참조 문서

작업 전 필요한 문서를 먼저 읽는다.

- 제품/범위: `docs/references/PRD.md`, `docs/references/MVP_SCOPE.md`
- 아키텍처: `docs/ARCHITECTURE.md`
- 설계 결정: `docs/ADR.md`
- 기능별 계약: `docs/specs/`
- 현재 DB 요약: `docs/generated/db-schema.md`

## 기술 스택

- Frontend: Next.js, TypeScript, shadcn, Tailwind CSS
- Backend: FastAPI, Python 3.11+
- Database: Supabase / PostgreSQL, SQLAlchemy ORM, Alembic
- AI: OpenAI GPT-4o mini
- Carbon accounting: ecologits
- File storage: local filesystem for MVP, S3-compatible storage for production

## 핵심 아키텍처 규칙

- OpenAI와 ecologits 호출은 `services/`에서만 처리하고 `routers/`에서 직접 호출하지 않는다.
- 토큰 차감과 보상 계산은 `services/reward.py`, `services/daily_reset.py` 경계 안에서만 처리한다.
- 파일 저장은 `services/storage.py`의 `FileStorage` 인터페이스를 통해서만 처리한다.
- 클라이언트 컴포넌트에서 OpenAI, ecologits, Supabase service role key 등 외부 API/비밀 키를 직접 호출하지 않는다.
- `routers/`는 입력 검증 후 service 호출만 담당하고 비즈니스 로직을 두지 않는다.
- API 요청/응답은 `schemas/`의 Pydantic 스키마를 사용한다.
- DB 모델 변경 시 Alembic migration을 함께 작성한다.

## 협업 담당 영역

| Owner | Area | Features |
| --- | --- | --- |
| 장태환 | Backend | 사용자 인증, 온보딩, 채팅 API, ecologits 연동 |
| 김찬혁 | Backend | 챌린지 생성, 챌린지 사진 인증, 파일 업로드 |

담당자 지정 규칙:

- 회원가입, 로그인, 로그아웃, JWT, 온보딩, 채팅, OpenAI/ecologits 이슈는 장태환을 owner로 지정한다.
- 챌린지 생성, 챌린지 수락/완료, 사진 인증, 파일 저장, 업로드 이슈는 김찬혁을 owner로 지정한다.
- 토큰 보상/차감처럼 영역이 만나는 작업은 primary owner와 reviewer를 함께 지정한다.

## 개발 규칙

- 새 기능은 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성한다.
- 변경 범위는 GitHub issue 또는 `docs/exec-plans/active/*`에 맞춘다.
- 관련 없는 기능 추가나 리팩터링을 하지 않는다.
- 브랜치는 `{owner-id}/{type}/{issue-number}/{slug}` 형식을 따른다. 예: `743hw4n/feat/1/signup`
- 커밋 메시지는 conventional commits 형식을 따른다. 예: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

## Workflows, Agents, Skills

- Issue workflow: `.agents/workflows/issue-workflow.md`
- Implementation agent: `.agents/agents/implementation-agent.md`
- Test agent: `.agents/agents/test-agent.md`
- Review agent: `.agents/agents/review-agent.md`
- Issue creation skill: `.agents/skills/issue-create/SKILL.md`
- PR creation skill: `.agents/skills/pr-create/SKILL.md`
- FastAPI skill: `.agents/skills/fastapi/SKILL.md`

## Commands

```bash
# Backend development server
python3 -m uvicorn app.main:app --reload

# Python tests
python3 -m pytest

# Frontend development server
npm run dev

# Frontend production build
npm run build

# Frontend lint
npm run lint

# Frontend tests
npm run test
```
