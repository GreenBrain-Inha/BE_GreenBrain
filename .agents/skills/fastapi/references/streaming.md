# Streaming Patterns

Streaming은 기능이 점진적 응답을 명확히 요구할 때만 사용한다.

## GreenBrain 기본값

- Chat streaming은 별도 spec이 추가되기 전까지 MVP 범위가 아니다.
- binary file 응답이 필요하면 적절한 response class를 명시하고 storage 접근은 `services/storage.py` 뒤에 둔다.
- 클라이언트에 raw storage path나 secret을 반환하지 않는다.
