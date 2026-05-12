# Issue Workflow

사용자가 새 기능 구현, 버그 수정, 또는 이슈 기반 백엔드 작업을 요청하면 이 workflow를 사용한다.

## 1. 문서 확인

계획이나 구현 전에 공통 지침과 관련 문서를 읽는다.

- `AGENTS.md`
- `docs/references/PRD.md`
- `docs/references/MVP_SCOPE.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- 관련 `docs/specs/` 문서

## 2. 이슈 생성

`.agents/skills/issue-create/SKILL.md`를 사용한다.

이슈에는 다음을 포함한다.

- 담당자와 리뷰어
- 목표
- 범위
- 제외 범위
- API 계약 또는 동작 계약
- 인수 기준
- 테스트 명령

## 3. 실행 계획 생성

`docs/exec-plans/active/{issue-number}-{slug}.md`를 생성한다.

실행 계획에는 다음을 포함한다.

- 참조 문서
- 담당자와 리뷰어
- 구현 단계
- 테스트 계획
- 리뷰 체크리스트

실행 계획은 이슈 범위 안으로 제한한다. 관련 없는 리팩터링을 추가하지 않는다.

## 4. 브랜치 생성

브랜치 형식:

```text
{owner-id}/{type}/{issue-number}/{slug}
```

예시:

```text
743hw4n/feat/1/signup
743hw4n/fix/12/login-lockout
```

## 5. 구현

`.agents/agents/implementation-agent.md`를 사용한다.

FastAPI 작업에는 `.agents/skills/fastapi/SKILL.md`를 함께 적용한다.

## 6. 테스트

`.agents/agents/test-agent.md`를 사용한다.

기본 명령:

```bash
python3 -m pytest
```

테스트가 실패하면 구현 단계로 돌아가 이슈 범위 안에서 수정한다.

## 7. 리뷰

`.agents/agents/review-agent.md`를 사용한다.

리뷰를 통과해야 PR을 생성한다.

## 8. PR 생성과 Push

`.agents/skills/pr-create/SKILL.md`를 사용한다.

PR 본문에는 다음을 포함한다.

- 관련 이슈
- 담당자와 리뷰어
- 요약
- 변경 사항
- 실행한 테스트
- 남은 위험 또는 후속 작업

PR 생성 후 실행 계획을 `docs/exec-plans/active/`에서 `docs/exec-plans/completed/`로 이동한다.
