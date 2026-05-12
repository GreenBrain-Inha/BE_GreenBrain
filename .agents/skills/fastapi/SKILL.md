---
name: fastapi
description: GreenBrain 백엔드의 FastAPI router, dependency, Pydantic schema, response model, API 테스트를 구현하거나 리뷰할 때 사용한다.
---

# FastAPI Skill

이 skill은 FastAPI 공식 agent skill을 GreenBrain에 맞게 축약한 것이다.

출처: https://github.com/fastapi/fastapi/blob/master/fastapi/.agents/skills/fastapi/SKILL.md

공식 FastAPI 지침과 GreenBrain 아키텍처 규칙이 충돌하면 GreenBrain 규칙을 우선한다.

## 사용 시점

FastAPI router, dependency, Pydantic schema, response model, API 테스트, HTTP 동작 변경이 포함된 백엔드 작업에서 사용한다.

## GreenBrain 규칙

- router는 얇게 유지한다: 입력 검증, 의존성 연결, service 호출, schema 기반 응답 반환만 담당한다.
- 비즈니스 로직은 `services/`에 둔다.
- 요청/응답 Pydantic 모델은 `schemas/`에 둔다.
- 민감 정보 노출을 막기 위해 return type 또는 `response_model`을 사용한다.
- 응답 body에 `password`, `password_hash`, JWT, API key, service role key를 포함하지 않는다.
- SQLAlchemy model이나 DB 제약조건이 바뀌면 Alembic migration을 함께 작성한다.
- 테스트에서는 OpenAI, ecologits, storage를 mock 처리한다.

## 작업 절차

1. `AGENTS.md`, 관련 spec, active exec plan을 읽는다.
2. 변경이 router, schema, service, model, migration 중 어디에 속하는지 먼저 나눈다.
3. API 또는 service 동작을 증명하는 테스트를 먼저 작성한다.
4. 타입이 명시된 request/response 모델로 구현한다.
5. `python3 -m pytest` 또는 더 좁은 관련 테스트 명령을 실행한다.

## FastAPI 구현 규칙

- `Path`, `Query`, `Header`, `Cookie`, `Body`, `Depends`에는 `typing.Annotated`를 우선 사용한다.
- 자주 쓰는 dependency는 재사용 가능한 타입 alias로 만든다.
- path operation이나 Pydantic model에서 required 표시를 위해 `...`를 쓰지 않는다.
- 가능한 경우 return type annotation을 사용한다.
- 실제 반환 객체와 공개 응답 모델이 다르면 decorator의 `response_model`을 사용한다.
- router 단위 `prefix`, `tags`, 공통 dependency는 `APIRouter`에 둔다.
- 하나의 함수에 여러 HTTP operation을 섞지 않는다.
- 호출하는 코드가 non-blocking이고 `await`되는 경우에만 `async def`를 사용한다. 확실하지 않거나 blocking/sync 코드면 일반 `def`를 사용한다.
- 새 코드에서 `ORJSONResponse`, `UJSONResponse`를 직접 사용하지 않는다. 타입이 지정된 응답과 Pydantic 직렬화를 우선한다.
- 일반 type annotation과 validation으로 충분하면 Pydantic `RootModel`을 사용하지 않는다.

## References

- Dependency 패턴: `references/dependencies.md`
- Streaming 패턴: `references/streaming.md`
- 도구와 관련 라이브러리: `references/other-tools.md`
