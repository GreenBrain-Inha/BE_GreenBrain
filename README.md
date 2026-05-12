# GreenBrain

AI 챗봇 사용량을 탄소 토큰으로 환산하고, 토큰 소진 시 실생활 챌린지 수행으로 토큰을 회복하는 탄소 책임 서비스.

---

## 팀

| 이름 | 역할 |
|---|---|
| 장태환 | Backend — 사용자 인증, 온보딩, 채팅 API, ecologits |
| 김찬혁 | Backend — 챌린지 생성, 인증, 파일 업로드 |

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| Frontend | Next.js, TypeScript, shadcn, Tailwind CSS |
| Backend | FastAPI (Python 3.11+) |
| DB | Supabase / PostgreSQL, SQLAlchemy, Alembic |
| LLM | OpenAI GPT-4o mini |
| 탄소 계산 | ecologits |
| 파일 저장 | 로컬 FS (MVP) → S3 호환 (프로덕션) |

---

## 시작하기

### 사전 준비

- Python 3.11+

### 설치

```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Git hook 설치
pre-commit install
```

### 환경 변수

`.env.example`을 복사해 `.env`를 만들고 값을 채운다.

```bash
cp .env.example .env
```

### DB 마이그레이션

```bash
alembic upgrade head
```

---

## 개발 명령어

```bash
# 백엔드 서버 실행
python3 -m uvicorn app.main:app --reload

# Python 테스트
python3 -m pytest
```

---

## 프로젝트 구조

```
.
├── app/                  # FastAPI 백엔드
│   ├── routers/          # HTTP 엔드포인트 (입력 검증 → service 호출)
│   ├── services/         # 비즈니스 로직
│   ├── models/           # SQLAlchemy ORM 모델
│   ├── schemas/          # Pydantic 요청/응답 스키마
│   └── db/               # DB 세션, Alembic 마이그레이션
├── tests/                # pytest 테스트
├── docs/                 # references, architecture, specs, exec plans, generated docs
├── .agents/              # 공통 agent workflow, agent, skill 정의
└── scripts/              # 유틸리티 스크립트
```

---

## 주요 플로우

```
채팅 → ecologits 탄소 계산 → 토큰 차감
  ↓ (토큰 소진)
챌린지 자동 생성 (생활 습관 프로필 기반)
  ↓ (사진 업로드)
즉시 토큰 +20 회복
  ↓ (커뮤니티 좋아요 3개마다)
토큰 +20 추가 회복 (하루 최대 60)
```

---

## 참고 문서

- [PRD](docs/references/PRD.md) — 제품 요구사항
- [MVP Scope](docs/references/MVP_SCOPE.md) — MVP 포함/제외 범위
- [Architecture](docs/ARCHITECTURE.md) — 아키텍처 및 데이터 모델
- [ADR](docs/ADR.md) — 설계 결정 기록
