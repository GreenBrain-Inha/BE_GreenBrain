# GreenBrain MVP Scope

This document keeps implementation agents focused on the MVP loop.

## In Scope

- Email/password signup.
- Login and logout with JWT in an HttpOnly cookie.
- Onboarding survey for transport, diet, and housing profile data.
- GPT-4o mini chat through the FastAPI backend.
- Message-level carbon calculation through ecologits.
- Daily KST carbon token state and token deduction.
- Token exhaustion handling.
- Automatic challenge generation when tokens are exhausted.
- Challenge acceptance and completion through one verification photo.
- Local filesystem photo storage for MVP.
- Verification feed with likes.
- Like milestone reward logic after verification photo upload.

## Out of Scope

- Social login.
- Email verification.
- Password reset.
- Native mobile apps.
- AI vision-based photo verification.
- Friends, follows, or private social graph.
- Weekly/monthly analytics dashboards.
- Custom user-created challenges.
- Carbon credit purchase or offset integrations.
- Production S3 setup unless explicitly scoped by an issue.

## MVP Completion Signal

The MVP is complete when a user can complete this loop end to end:

```text
signup/login -> onboarding -> chat -> carbon token deduction -> token exhaustion
-> challenge -> photo upload -> token recovery -> feed likes -> additional token recovery
```
