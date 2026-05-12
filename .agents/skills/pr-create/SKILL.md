---
name: pr-create
description: GreenBrain 구현, 테스트, 리뷰가 끝난 뒤 Pull Request 또는 PR 본문 초안을 만들 때 사용한다. issue workflow의 마지막 단계에서 사용한다.
---

# PR Create Skill

## 사용 시점

구현, 테스트, 리뷰가 끝났고 PR을 만들 준비가 되었을 때 사용한다.

## 필수 입력

- 관련 GitHub issue
- 현재 작업의 `docs/exec-plans/active/*`
- 리뷰 결과
- 테스트 명령 출력
- git diff 요약
- `.github/PULL_REQUEST_TEMPLATE.md`

## 작업 절차

1. 리뷰에 blocking finding이 없는지 확인한다.
2. 테스트 실행 여부와 정확한 명령을 확인한다.
3. `.github/PULL_REQUEST_TEMPLATE.md`의 섹션 이름을 유지한다.
4. 변경 사항은 파일 나열보다 동작 기준으로 요약한다.
5. migration, generated docs, API 계약 변경이 있으면 명시한다.
6. PR 생성 후 완료된 실행 계획을 `docs/exec-plans/completed/`로 이동한다.

## PR 본문 형식

`.github/PULL_REQUEST_TEMPLATE.md`의 형식을 그대로 사용한다.

```md
Closes #{issue-number}

## Summary

{요약}

Owner: {담당자}
Reviewer: {리뷰어 또는 N/A}

## Changes

- {동작 기준 변경 사항 1}
- {동작 기준 변경 사항 2}

## Etc

Tests:
- `{실행한 테스트 명령}` 결과: {통과/실패/생략}

Risks / Follow-ups:
- {남은 위험 또는 후속 작업. 없으면 N/A}
```

## 금지/주의 규칙

- `.github/PULL_REQUEST_TEMPLATE.md`의 기본 섹션 이름을 바꾸지 않는다.
- 테스트와 리뷰가 끝나기 전에 PR을 만들지 않는다.
- 생략한 테스트가 있으면 숨기지 말고 이유를 적는다.
- 후속 작업은 현재 PR 범위와 분리해서 적는다.
