---
name: issue-create
description: GreenBrain 기능 요청, 버그 리포트, spec, 실행 계획 논의를 GitHub issue 또는 issue 초안으로 정리할 때 사용한다. 구현 시작 전에 사용한다.
---

# Issue Create Skill

## 사용 시점

구현 전에 GitHub issue를 만들거나 issue 본문 초안을 작성해야 할 때 사용한다.

## 필수 입력

- `AGENTS.md`
- `docs/references/PRD.md`
- `docs/references/MVP_SCOPE.md`
- 관련 `docs/specs/*`
- API, DB, service 경계가 관련되면 `docs/ARCHITECTURE.md`
- `.github/ISSUE_TEMPLATE/-feature.md`
- `.github/ISSUE_TEMPLATE/-fix.md`
- `.github/ISSUE_TEMPLATE/-chore.md`

## 작업 절차

1. `AGENTS.md` 기준으로 기능 영역과 담당자를 정한다.
2. 작업 유형에 맞는 `.github/ISSUE_TEMPLATE/*` 템플릿을 선택한다.
3. 관련 spec과 architecture 문서를 읽는다.
4. 한 PR로 끝낼 수 있을 만큼 이슈 범위를 작게 잡는다.
5. 템플릿의 섹션 이름을 유지하면서 범위, 인수 기준, 테스트 명령을 채운다.

## 템플릿 선택 기준

- 기능 추가: `.github/ISSUE_TEMPLATE/-feature.md`
- 버그 수정: `.github/ISSUE_TEMPLATE/-fix.md`
- 문서, 설정, 하네스, 정리 작업: `.github/ISSUE_TEMPLATE/-chore.md`

## Feature/Chore 본문 형식

`.github` 템플릿의 섹션을 그대로 사용한다.

```md
## ✏️Summary

{작업 요약}

Owner: {담당자}
Reviewer: {리뷰어 또는 N/A}

## 📝 ToDo

- [ ] {구현 또는 문서 작업 1}
- [ ] {구현 또는 문서 작업 2}
- [ ] {테스트 또는 검증}
- [ ] {필요 시 docs/generated 또는 migration 갱신}

## 📚 Other information

Scope:
- {포함 범위}

Out of Scope:
- {제외 범위}

Acceptance Criteria:
- {인수 기준}

Test Plan:
- `python3 -m pytest`
```

## Fix 본문 형식

```md
## ✏️ Summary

{수정 요약}

Owner: {담당자}
Reviewer: {리뷰어 또는 N/A}

## 🚨 Bug Description

{증상, 기대 동작, 실제 동작, 재현 조건}

## 📝 ToDo

- [ ] {실패 재현 테스트}
- [ ] {수정 작업}
- [ ] {회귀 테스트}

## 📚 Other information

Scope:
- {포함 범위}

Out of Scope:
- {제외 범위}

Acceptance Criteria:
- {인수 기준}

Test Plan:
- `python3 -m pytest`
```

## 금지/주의 규칙

- `.github/ISSUE_TEMPLATE`의 기본 섹션 이름을 바꾸지 않는다.
- 관련 없는 리팩터링을 포함하지 않는다.
- 테스트 없이 구현으로 바로 넘어가는 계획을 만들지 않는다.
- 백엔드 작업의 기본 테스트 명령은 `python3 -m pytest`로 둔다.
- 장태환/김찬혁 담당 영역이 겹치면 primary owner와 reviewer를 함께 지정한다.
