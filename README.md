# LLM 채용 지원자 분석 시스템

> LangChain/LangGraph 기반 RAG 문서 검색 및 지원자 분석 시스템

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.9-green.svg)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.50-orange.svg)](https://langchain-ai.github.io/langgraph/)

## 📋 주요 기능

1. **RAG 문서 검색** (LangChain LCEL Chain)
   - PDF/DOCX/TXT/XLSX 업로드 → Qdrant 벡터 검색
   - Few-shot 학습 기반 LLM 답변 생성
   - LangSmith 자동 추적

2. **Two-Tier Intent Classification** (LangGraph Workflow)
   - Tier 1: 키워드 매칭 (빠른 응답, < 100ms)
   - Tier 2: LLM 기반 분류 (fallback, 2-5초)
   - 상태 기계 시각화

3. **지원자 분석**
   - 자기소개서 요약, 키워드 추출
   - AI 기반 면접 질문 생성

4. **자연어 SQL**
   - 질의 → SQL 변환 → 결과 해석
   - 패턴 매칭 기반 (SQL injection 방지)

5. **Few-shot 학습 루프**
   - Query Logs 자동 수집
   - 관리 UI에서 Few-shot 승격
   - PostgreSQL Trigger 기반 변경 이력 추적

---

## 🏗️ 아키텍처

```
사용자 질의
    ↓
LangGraph ChatGraph (워크플로)
    ├─ check_intent_table (Tier 1: 키워드 매칭)
    ├─ classify_with_llm (Tier 2: LLM 분류)
    └─ route_by_intent
        ↓
LangChain LCEL Chains
    ├─ RAGChain (Qdrant + Ollama + Few-shot)
    ├─ SQLAgent (자연어 → SQL)
    └─ General (일반 대화)
        ↓
LangSmith Tracing (자동)
    ↓
응답 반환 + Query Log 저장
```

---

## 🚀 빠른 시작

### 1. 환경 변수 설정

```bash
# .env 파일 생성
cp backend/.env.example backend/.env

# backend/.env 파일 수정
# LANGCHAIN_API_KEY를 자신의 LangSmith API 키로 교체
# https://smith.langchain.com 에서 무료 발급
```

### 2. Docker Compose로 전체 스택 실행

```bash
# PostgreSQL, Ollama, Qdrant, Backend, Frontend 자동 시작
docker-compose -f docker-compose.dev.yml up -d

# Ollama 모델 다운로드 (최초 1회)
docker exec -it ollama ollama pull llama3.2:1b

# 로그 확인
docker-compose logs -f backend
```

### 3. 접속

- **Frontend**: http://localhost
- **Backend API 문서**: http://localhost:8000/docs
- **LangSmith 대시보드**: https://smith.langchain.com → Projects → llmproject-phase2

---

## 🛠️ 기술 스택

### Backend
- **Framework**: FastAPI, SQLModel
- **LLM**: Ollama (llama3.2:1b)
- **Vector DB**: Qdrant + FastEmbed (ONNX, 778MB)
- **DB**: PostgreSQL 16
- **LangChain**: 0.3.9 (LCEL, Chains, Prompts)
- **LangGraph**: 0.2.50 (State Machine Workflow)
- **LangSmith**: 0.1.145 (Tracing & Monitoring)

### Frontend
- **Framework**: React 19, TypeScript
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 4

---

## 📂 프로젝트 구조

```
backend/app/
├── chains/           # LangChain LCEL Chains
│   └── rag_chain.py  # RAG Chain (200줄 → 50줄)
├── graphs/           # LangGraph 워크플로
│   └── chat_graph.py # ChatGraph (Two-Tier Intent)
├── services/         # 비즈니스 로직 (Phase 1 호환)
│   ├── query_router.py
│   ├── rag_service.py
│   ├── sql_agent.py
│   └── ollama_service.py
├── api/              # FastAPI 엔드포인트
└── models/           # SQLModel 데이터 모델
```

---

## 💡 Phase 1 vs Phase 2 개선점

| 항목 | Phase 1 (커스텀) | Phase 2 (LangChain) |
|------|-----------------|-------------------|
| **RAG 구현** | 직접 구현 (~200줄) | LCEL Chain (~50줄) |
| **워크플로** | if/else 분기 | LangGraph 시각화 |
| **디버깅** | print() 로그 | LangSmith 대시보드 |
| **추적** | 수동 로깅 | 자동 추적 |
| **확장성** | 수동 체인 관리 | 표준 프레임워크 |
| **의존성 크기** | 767MB | ~1.2GB |

**개선점:**
- ✅ LCEL 파이프라인으로 코드 75% 감소
- ✅ LangGraph로 워크플로 시각화 및 디버깅 용이
- ✅ LangSmith로 자동 추적 (프롬프트, 응답 시간, 에러)
- ✅ LangChain 생태계 통합 (커뮤니티, 문서, 업데이트)

**Trade-offs:**
- ⚠️ 의존성 50% 증가 (폐쇄망 배포 시 고려)
- ⚠️ 학습 곡선 (프레임워크 이해 필요)

---

## 🔧 개발 가이드

### 로컬 개발 (Docker)

```bash
# 전체 스택 시작
docker-compose -f docker-compose.dev.yml up -d

# 백엔드만 재시작
docker-compose restart backend

# 로그 확인
docker-compose logs -f backend

# 중지
docker-compose -f docker-compose.dev.yml down
```

### 로컬 개발 (Python/Node 직접)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install && npm run dev
```

### LangSmith 디버깅

1. https://smith.langchain.com → Projects → llmproject-phase2
2. 각 요청의 ChatGraph 노드별 입/출력 확인
3. LCEL Chain 단계별 처리 시간 확인

---

## 📚 문서

- **[CLAUDE.md](CLAUDE.md)** - 개발 가이드 (아키텍처, 패턴, 디버깅)
- **[DEPLOY.md](DEPLOY.md)** - 폐쇄망 배포 가이드

---

## 📝 라이선스

MIT License

---

**LangChain/LangGraph로 진화한 RAG 시스템 🚀**
