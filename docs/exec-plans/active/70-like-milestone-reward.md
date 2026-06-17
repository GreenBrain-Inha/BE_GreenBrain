# Issue 70: Like Milestone Reward Only

## References

- GitHub issue: https://github.com/GreenBrain-Inha/BE_GreenBrain/issues/70
- `AGENTS.md`
- `docs/references/PRD.md`
- `docs/references/MVP_SCOPE.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/specs/challenge-photo-upload.md`
- `docs/specs/challenge-likes.md`
- `docs/specs/challenge-feed.md`
- `docs/generated/db-schema.md`

## Owner / Reviewer

- Owner: 김찬혁
- Reviewer: 장태환

## Goal

Remove immediate token rewards from challenge photo upload. Token rewards for challenge verification photos must be granted only when other users' likes reach a 3-like milestone.

## Scope

- Stop granting upload rewards in the challenge photo upload service path.
- Keep challenge completion and photo feed creation behavior unchanged.
- Preserve existing like milestone reward behavior for 3, 6, 9... likes.
- Update API schemas, tests, and documentation that still describe upload rewards.

## Out of Scope

- Like cancellation.
- AI photo verification.
- Reward amount or daily like reward cap changes.
- Frontend UI redesign.

## Implementation Steps

1. Add or update tests proving photo upload does not change token balance or create an `upload_reward` transaction.
2. Update `challenge_photo_service` and related schemas so upload success does not call upload reward logic.
3. Keep like milestone reward tests passing and add coverage if the 3-like behavior is not explicit enough.
4. Update PRD, MVP scope, and photo upload spec to remove immediate upload reward language.
5. Run focused tests, then the full backend pytest suite if feasible.

## Acceptance Criteria

- Uploading a challenge photo completes the challenge and creates the photo row.
- Uploading a challenge photo does not increase `daily_token_state.tokens_remaining`.
- Uploading a challenge photo does not create a `token_transactions` row with `type = 'upload_reward'`.
- A reward is granted only when other users' likes reach the 3-like milestone.
- Existing anti-abuse rules for likes remain unchanged.

## Test Plan

- `python3 -m pytest tests/test_challenge_photo_upload.py tests/test_like_rewards.py`
- `python3 -m pytest`

## Review Checklist

- Router remains thin; business logic stays in services.
- Token reward changes stay inside reward/token service boundaries.
- No DB schema or migration change is introduced unless the implementation requires it.
- API responses do not expose internal file paths or sensitive values.
- Documentation matches the implemented reward policy.
