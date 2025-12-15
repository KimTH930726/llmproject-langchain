# LLM 채용 지원자 분석 시스템 - Phase 2 (LangChain/LangGraph)

> **Phase 1에서 Phase 2로 진화**: 커스텀 RAG → LangChain/LangGraph 기반 고급 워크플로

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.9-green.svg)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.50-orange.svg)](https://langchain-ai.github.io/langgraph/)

## 🎯 Phase 2 목표

Phase 1의 커스텀 RAG 구현을 LangChain/LangGraph로 마이그레이션하여 표준화된 프레임워크의 이점을 활용합니다.

- ✅ **LangChain LCEL**로 RAG Chain 재구현 (200줄 → 50줄)
- ✅ **LangGraph**로 복잡한 워크플로 시각화
- ✅ **LangSmith**로 추적 및 모니터링 (무료 Developer 플랜)
- ✅ **Phase 1 DB 스키마**와 100% 호환

---

## 🏗️ 아키텍처 비교

### Phase 1 (커스텀 RAG) - 기존
```
사용자 질의
    ↓
QueryRouter (커스텀 구현)
    ├─ intents 테이블 확인 (Tier 1)
    └─ LLM 분류 (Tier 2)
    ↓
RAGService/SQLAgent (커스텀 구현)
    ├─ Qdrant 검색
    ├─ Few-shot 주입
    └─ Ollama 호출
    ↓
응답 반환
```

### Phase 2 (LangChain/LangGraph) - 목표
```
사용자 질의
    ↓
LangGraph ChatGraph (워크플로 시각화)
    ├─ check_intent_table (Tier 1)
    ├─ classify_with_llm (Tier 2)
    └─ route_by_intent
    ↓
LangChain Chains (LCEL)
    ├─ RAGChain (Qdrant + Ollama)
    ├─ SQLChain (LangChain SQL Agent)
    └─ GeneralChain (Few-shot + Ollama)
    ↓
LangSmith Tracing (자동 추적)
    ↓
응답 반환
```

---

## 🚀 빠른 시작

### 1. 환경 변수 설정

```bash
# .env 파일 생성
cp backend/.env.example backend/.env

# backend/.env 파일 수정
# LANGCHAIN_API_KEY를 자신의 LangSmith API 키로 교체
# https://smith.langchain.com 에서 발급
```

### 2. 전체 스택 실행

```bash
# Docker Compose로 실행 (PostgreSQL, Ollama, Qdrant, Backend, Frontend)
docker-compose -f docker-compose.dev.yml up -d

# Ollama 모델 다운로드 (최초 1회)
docker exec -it ollama ollama pull llama3.2:1b
```

### 3. 접속

- **Frontend**: http://localhost
- **Backend API 문서**: http://localhost:8000/docs
- **LangSmith 대시보드**: https://smith.langchain.com → Projects → llmproject-phase2

---

## 📊 마이그레이션 현황

### ✅ 완료
- [x] Phase 1 코드베이스 복사
- [x] Git 저장소 초기화 및 GitHub 푸시
- [x] LangChain 의존성 추가 (LangChain 0.3.9, LangGraph 0.2.50, LangSmith 0.1.145)
- [x] README 작성
- [x] **LangSmith 설정** - API 키 발급 및 .env 설정 완료
- [x] **RAG Chain 구현** (`chains/rag_chain.py`) - LCEL 기반, Few-shot 통합
- [x] **ChatGraph 구현** (`graphs/chat_graph.py`) - Two-Tier Intent Classification 워크플로
- [x] **API 엔드포인트 통합** (`api/chat.py`) - ChatGraph로 변경, LangSmith 추적 활성화

### 🚧 진행 중
- [ ] SQL Chain 구현 (`chains/sql_chain.py`)
- [ ] Hybrid Search Graph 구현 (`graphs/hybrid_graph.py`)
- [ ] Docker 환경 테스트
- [ ] LangSmith 추적 검증

---

## 📚 문서

| 문서 | 설명 | 상태 |
|------|------|------|
| [LANGCHAIN_MIGRATION_PLAN.md](LANGCHAIN_MIGRATION_PLAN.md) | 전체 마이그레이션 계획 | ✅ 완료 |
| [PHASE2_SETUP_GUIDE.md](PHASE2_SETUP_GUIDE.md) | 초기 설정 가이드 | ✅ 완료 |
| `docs/CHAINS_GUIDE.md` | LangChain Chains 구현 | 🚧 작성 예정 |
| `docs/GRAPHS_GUIDE.md` | LangGraph 워크플로 | 🚧 작성 예정 |
| `docs/LANGSMITH_GUIDE.md` | LangSmith 사용법 | 🚧 작성 예정 |

---

## 💡 Phase 1 vs Phase 2 비교

| 항목 | Phase 1 (커스텀) | Phase 2 (LangChain) |
|------|-----------------|-------------------|
| **RAG 구현** | 직접 구현 (~200줄) | LCEL Chain (~50줄) |
| **워크플로** | if/else 분기 | LangGraph 시각화 |
| **SQL Agent** | 패턴 매칭 (~300줄) | LangChain SQL Agent (~10줄) |
| **디버깅** | print() 로그 | LangSmith 대시보드 |
| **추적** | 수동 로깅 | 자동 추적 |
| **프롬프트 관리** | 하드코딩 | PromptTemplate |
| **Few-shot** | DB에서 수동 조회 | LangSmith Dataset |
| **배포** | 폐쇄망 최적화 | 클라우드 권장 |
| **의존성 크기** | 767MB | ~1.2GB |
| **학습 곡선** | 낮음 (직접 구현) | 중간 (프레임워크) |

---

## 🔗 관련 프로젝트

- **Phase 1 (커스텀 RAG)**: 별도 저장소 - 폐쇄망 배포용 경량 RAG
- **Phase 2 (LangChain)**: 현재 저장소 - LangChain/LangGraph 학습 및 확장

---

## 🛠️ 기술 스택

### Phase 1에서 유지
- **Backend**: FastAPI, SQLModel, Qdrant, FastEmbed, Ollama
- **Frontend**: React 19, TypeScript, Vite 7, Tailwind CSS 4
- **DB**: PostgreSQL 16, Qdrant
- **LLM**: Ollama (llama3.2:1b)

### Phase 2에서 추가
- **LangChain**: 0.3.9 (LCEL, Chains, Prompts)
- **LangGraph**: 0.2.50 (Workflow Orchestration)
- **LangSmith**: 0.1.145 (Tracing & Monitoring)
- **LangChain Integrations**: Ollama, Qdrant, SQL

---

## 📋 주요 기능 (Phase 1 기능 유지)

1. **지원자 분석**
   - 요약, 키워드 추출, 면접 질문 생성

2. **RAG 문서 검색**
   - PDF/DOCX/TXT/XLSX 업로드
   - Qdrant 벡터 검색
   - LLM 기반 답변 생성

3. **자연어 SQL**
   - 자연어 질의 → SQL 변환
   - DB 조회 → 결과 해석

4. **Intent & Few-shot**
   - Two-Tier Intent Classification
   - Few-shot Learning
   - Query Logs 관리

5. **Multi-Stage RAG**
   - Query Decomposition (비정형/정형 분류)
   - Relevance Analysis (연관성 분석)

---

## 🔧 개발 가이드

### 로컬 개발 (Python/Node 직접 실행)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Docker 개발 (권장)

```bash
# 전체 스택 시작
docker-compose -f docker-compose.dev.yml up -d

# 로그 확인
docker-compose logs -f backend

# 재시작
docker-compose restart backend

# 중지
docker-compose -f docker-compose.dev.yml down
```

---

## 🎯 다음 단계

1. **LangSmith 설정**
   - https://smith.langchain.com 계정 생성
   - API 키 발급
   - `backend/.env`에 API 키 설정

2. **Phase 2-1: RAG Chain 구현**
   - `backend/app/chains/rag_chain.py` 생성
   - LangChain LCEL로 재구현
   - API에서 RAGChain 사용
   - LangSmith에서 추적 확인

3. **Phase 2-2: ChatGraph 구현**
   - `backend/app/graphs/chat_graph.py` 생성
   - Two-Tier Intent Classification 그래프화
   - 워크플로 시각화

---

## 🤝 기여

Phase 2는 개인 학습 프로젝트이지만, 피드백과 제안은 언제나 환영합니다!

---

## 📝 라이선스

MIT License

---

**Phase 1 → Phase 2 진화 중! 🚀**
