# RunYourAI 모델 라우팅 스펙

## Summary

GreenBrain 채팅은 RunYourAI API Router를 통해 OpenAI, Anthropic, Google Gemini 등 여러 provider 모델을 호출한다. 프론트는 메시지 전송 시 `model_id`를 넘기고, 백엔드는 해당 모델로 RunYourAI Chat Completions API를 호출한다.

RunYourAI 연동은 OpenAI SDK 호환 방식을 사용한다.

- Base URL: `https://api.runyour.ai/v1`
- API key env: `RUNYOUR_API_KEY`
- Chat endpoint: `POST /v1/chat/completions`
- Model format: `provider/model-name`
- Live model list check on 2026-05-18 returned 31 model IDs. The live Gemini prefix is `gemini/...`; `google/...` is a legacy alias used only in the carbon mapping.

## API Contract

### 모델 목록 조회

`GET /api/chat/models`

- 인증 필요
- 백엔드가 `client.models.list()`로 RunYourAI의 현재 모델 목록을 조회한다.
- Swagger에서 전체 모델 ID를 확인하고 채팅 전송 테스트에 사용할 수 있다.
- 응답은 모델 ID 문자열 리스트만 반환한다.

Response:

```json
{
  "items": [
    "openai/gpt-4.1-2025-04-14",
    "anthropic/claude-sonnet-4-6",
    "gemini/gemini-2.5-pro"
  ]
}
```

### 메시지 전송

`POST /api/chat/sessions/{session_id}/messages`

Request:

```json
{
  "message": "안녕",
  "model_id": "anthropic/claude-sonnet-4-6"
}
```

- `model_id` 생략 시 기본값은 `openai/gpt-4.1-2025-04-14`
- assistant 메시지에는 실제 사용한 `model_id`를 저장한다.
- 응답 body에도 `model_id`를 포함한다.

## Validation Policy

- `GET /api/chat/models`에서 반환된 모델 ID를 그대로 사용하는 것을 전제로 한다.
- provider가 `openai`, `anthropic`, `gemini`, `google` 중 하나면 허용한다.
- 그 외 provider는 모든 환경에서 `400 Unsupported chat model`을 반환한다.
- RunYourAI가 모델을 거부하거나 호출 실패 시 `502 AI provider failed to generate a response`를 반환한다.

## Carbon Accounting

- RunYourAI 응답의 `usage.completion_tokens`와 요청 latency를 사용해 ecologits로 gCO2eq를 계산한다.
- Provider 매핑:
  - `openai/...` -> ecologits `openai`
  - `anthropic/...` -> ecologits `anthropic`
  - `gemini/...` -> ecologits `google_genai`
  - `google/...` -> ecologits `google_genai` (legacy alias)
- ecologits가 모델을 지원하지 않거나 계산에 실패하면 `carbon_gco2eq=null`로 저장하고 기존 정책대로 토큰 차감을 건너뛴다.

## Frontend Usage

- 앱 시작 시 `GET /api/chat/models`로 모델 목록을 조회하고 프론트에서 캐싱한다.
- 유저가 모델을 선택하면 해당 ID를 `POST /api/chat/sessions/{session_id}/messages`의 `model_id`에 넣어 전송한다.

Live model IDs confirmed with `client.models.list()` on 2026-05-18:

```text
anthropic/claude-haiku-4-5
anthropic/claude-opus-4-5
anthropic/claude-opus-4-6
anthropic/claude-opus-4-7
anthropic/claude-sonnet-4-5
anthropic/claude-sonnet-4-6
deepseek/deepseek-chat
gemini/gemini-2.5-flash
gemini/gemini-2.5-flash-lite
gemini/gemini-2.5-pro
gemini/gemini-3-flash-preview
gemini/gemini-3-pro-image-preview
gemini/gemini-3.1-flash-image-preview
gemini/gemini-3.1-pro-preview
openai/gpt-4.1-2025-04-14
openai/gpt-5
openai/gpt-5-mini-2025-08-07
openai/gpt-5-nano-2025-08-07
openai/gpt-5.1
openai/gpt-5.2
openai/gpt-5.3-codex
openai/gpt-5.4-2026-03-05
openai/gpt-5.4-mini-2026-03-17
openai/gpt-5.4-nano-2026-03-17
openai/gpt-5.4-pro-2026-03-05
openai/gpt-5.5-2026-04-23
openai/gpt-5.5-pro-2026-04-23
openai/gpt-image-1.5
runyour/free
upstage/solar-pro2
upstage/solar-pro3
```

## Test Scenarios

- 모델 목록 조회가 RunYourAI 모델 ID 문자열 리스트를 반환한다.
- 모델 목록 조회 중 provider 오류가 발생하면 502를 반환한다.
- `model_id` 생략 시 기본 모델로 메시지를 전송한다.
- 허용된 provider 모델은 요청한 모델 ID로 응답한다.
- 허용되지 않은 provider 모델은 400으로 거부한다.
- carbon 지원 모델은 gCO2eq를 계산하고, 미지원 모델은 `null`로 저장한다.
