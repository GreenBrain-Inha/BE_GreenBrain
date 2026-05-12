# Dependency Patterns

FastAPI dependency는 다음 상황에서 사용한다.

- Pydantic validation만으로 표현할 수 없는 요청 준비 로직이 필요할 때
- DB 세션, 파일 핸들처럼 외부 리소스가 필요할 때
- `yield`로 cleanup이 필요할 때
- 여러 endpoint에서 공유되는 인증, 권한, early rejection 로직이 필요할 때

## GreenBrain 기본값

- DB session, current user 같은 공통 dependency는 재사용 가능한 `Annotated` alias를 우선 사용한다.
- DB session lifecycle은 router가 아니라 dependency에서 관리한다.
- dependency에는 비즈니스 workflow를 넣지 않는다. dependency는 service 호출에 필요한 입력, 리소스, 인증 상태를 준비하는 역할로 제한한다.
