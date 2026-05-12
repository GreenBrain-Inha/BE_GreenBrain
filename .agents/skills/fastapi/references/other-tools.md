# Tooling and Related Libraries

## GreenBrain 기본값

- 새 도구를 도입하기 전에 저장소의 기존 명령과 의존성 관리 방식을 우선한다.
- 기본 테스트 명령은 `python3 -m pytest`다.
- GreenBrain 아키텍처가 SQLAlchemy와 Alembic을 이미 선택했으므로 DB 작업에는 이를 사용한다.
- HTTP client나 API 테스트에는 이미 사용 가능한 경우 HTTPX를 우선한다.
- 명시적인 이슈 없이 lint, format, type-check, package manager를 새로 추가하지 않는다.
