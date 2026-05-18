# Tech Debt Tracker

Track deferred improvements that are outside the current issue scope.

Update 2026-05-17: SupabaseStorage is implemented with environment-based backend selection and mocked REST unit tests. Signed URL support remains a future option if the `challenge-photos` bucket becomes private.

| Date | Area | Debt | Reason Deferred | Follow-up |
| --- | --- | --- | --- | --- |
| 2026-05-15 | Storage | SupabaseStorage 실제 연동 보류 | 이번 PR은 로컬 개발 환경의 사진 업로드 흐름 검증이 목적이므로 LocalFileStorage만 구현 | Supabase bucket, service role key, public/signed URL 정책 확정 후 구현 |
