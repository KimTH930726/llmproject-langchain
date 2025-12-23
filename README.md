# Tool-based Agent RAG 시스템

> LangChain Tool Calling + LangGraph 기반 확장 가능한 RAG 시스템

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3.9-green.svg)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.50-orange.svg)](https://langchain-ai.github.io/langgraph/)

## 🎯 프로젝트 목적

**학습 중심의 현업 표준 패턴 구현**

- LangChain Tool Calling을 활용한 확장 가능한 Agent 아키텍처
- LangGraph를 통한 워크플로 시각화 및 디버깅
- 현업에서 많이 사용되는 ReAct Agent 패턴 학습
- DDD(Domain-Driven Design) 원칙 적용
- Lazy Initialization을 통한 메모리 최적화

## 📋 주요 기능

### 1. **Tool-based Agent** (핵심)
LLM이 사용자 질의를 분석하여 적절한 Tool을 자동 선택하고 실행합니다.

**사용 가능한 Tools:**
- `search_documents`: 업로드된 문서(PDF/DOCX/TXT/XLSX)에서 정보 검색
- `query_database`: 지원자 데이터베이스 조회 (SQL 쿼리 자동 생성)
- `general_conversation`: 일반 대화 및 시스템 안내

### 2. **확장 가능한 아키텍처**
새로운 기능 추가가 매우 간단합니다:

```python
# 새 Tool 정의만으로 기능 추가 완료!
@tool
async def new_feature_tool(query: str, session_context: Dict) -> str:
    """새 기능 설명"""
    # 로직 구현
    return result

# AVAILABLE_TOOLS 리스트에 추가
AVAILABLE_TOOLS.append(new_feature_tool)
# Agent가 자동으로 인식하고 사용!
```

### 3. **LangSmith 통합**
- 모든 Agent 실행이 자동으로 추적됨
- Tool 선택 과정, 실행 결과, 에러 추적
- 프롬프트 디버깅 및 성능 분석

### 4. **Few-shot Learning (Agent 레벨)**
- Query Logs에서 성공 케이스 자동 학습
- Agent 시스템 프롬프트에 예제 주입 (DDD 원칙)
- Tool 내부가 아닌 Agent 책임 영역

### 5. **메모리 최적화 (Lazy Loading)**
- Backend 시작 시간: 15초 → 3초
- 초기 메모리: 1.2GB → 400MB
- FastEmbed(778MB) 모델은 첫 사용 시에만 로드

---

## 🏗️ 아키텍처

```
사용자 질의 ("계약서에서 금액은?")
    ↓
LangGraph Agent (agent_graph.py)
    ├─ System Prompt (Few-shot 예제 포함)
    ├─ LLM Tool Calling (Ollama llama3.2:1b)
    └─ Tool 선택 추론
        ↓
ToolNode (자동 실행)
    ├─ search_documents → RAGChain → Qdrant 검색
    ├─ query_database → SQL Agent → PostgreSQL 조회
    └─ general_conversation → Ollama 직접 호출
        ↓
결과 반환 + Query Log 저장
    ↓
LangSmith 자동 추적
```

### 핵심 패턴

#### 1. **ReAct Agent Pattern** (현업 표준)
```python
# Agent 노드: Tool 선택
agent_node → LLM decides which tool to use

# Tool 노드: Tool 실행
tool_node → Execute selected tool

# 순환: Tool 결과를 보고 다시 추론
tool_node → agent_node → (반복 가능)
```

#### 2. **DDD 기반 책임 분리**
```
Agent 도메인:
- "어떻게 학습하는가" (Few-shot 프롬프트)
- "어떤 Tool을 선택하는가" (Tool calling)

Tool 도메인:
- "무엇을 하는가" (순수한 기능 실행)
- DB, 외부 API 호출 등
```

#### 3. **Lazy Initialization Pattern**
```python
# 무거운 리소스는 @property로 첫 사용 시에만 로드
@property
def embedding(self):
    if self._embedding is None:
        self._embedding = TextEmbedding(...)  # 778MB
    return self._embedding
```

#### 4. **Singleton Service Pattern**
```python
# 모듈 레벨 인스턴스 (FastAPI 라이프사이클 독립)
agent_graph = get_agent_graph()  # 싱글톤
rag_chain = get_rag_chain()      # 싱글톤
```

---

## 🚀 빠른 시작

### 1. 환경 변수 설정

```bash
# .env 파일 생성
cp backend/.env.example backend/.env

# backend/.env 파일 수정
LANGCHAIN_API_KEY=your_langsmith_key  # https://smith.langchain.com
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
QDRANT_URL=http://qdrant:6333
DATABASE_URL=postgresql://admin:admin123@postgres:5432/applicants_db
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
- **LLM**: Ollama (llama3.2:1b with Tool Calling)
- **Vector DB**: Qdrant + FastEmbed (ONNX, 778MB)
- **DB**: PostgreSQL 16
- **LangChain**: 0.3.9 (Tool Calling, LCEL Chains)
- **LangGraph**: 0.2.50 (ReAct Agent, ToolNode)
- **LangSmith**: 0.1.145 (Tracing)

### Frontend
- **Framework**: React 19, TypeScript
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 4

---

## 📂 프로젝트 구조

```
backend/app/
├── tools/                  # LangChain Tools
│   └── document_tools.py   # search_documents, query_database, general_conversation
├── graphs/                 # LangGraph 워크플로
│   └── agent_graph.py      # ReAct Agent (agent ↔ tools 순환)
├── chains/                 # LangChain LCEL Chains
│   └── rag_chain.py        # RAG Chain (Qdrant + Ollama, Lazy Init)
├── services/               # 비즈니스 로직
│   ├── sql_agent.py        # NL→SQL 변환
│   ├── ollama_service.py   # Ollama API 래퍼
│   └── qdrant_service.py   # Qdrant 연동 (Lazy Init)
├── api/                    # FastAPI 엔드포인트
│   ├── chat.py             # Tool-based Agent API
│   ├── upload.py           # 문서 업로드
│   ├── analysis.py         # 지원자 분석
│   └── query_log.py        # 대화 이력
└── models/                 # SQLModel 데이터 모델
```

**제거된 파일 (Tool-based로 전환):**
- ~~`api/intent.py`~~ - Intent 관리 API
- ~~`api/fewshot.py`~~ - Few-shot 관리 API
- ~~`services/query_router.py`~~ - Two-tier Intent Classification
- ~~`graphs/chat_graph.py`~~ - Intent 기반 워크플로
- ~~`models/few_shot.py`~~ - Intent, FewShot 모델

---

## 💡 설계 철학 & Trade-offs

### ✅ 장점 (현재 구조)

1. **확장성**: 새 Tool 추가 = 함수 하나 작성
2. **표준 패턴**: LangChain 생태계 표준 (문서, 커뮤니티 풍부)
3. **유연성**: LLM이 문맥 이해 후 Tool 선택 (키워드 제약 없음)
4. **디버깅**: LangSmith로 모든 단계 시각화
5. **DDD 준수**: 책임 분리 명확 (Agent vs Tool)
6. **메모리 효율**: Lazy Loading으로 시작 시간 5배 단축

### ⚠️ Trade-offs

1. **성능**: 모든 질의에서 LLM 호출 필요 (2-5초)
   - 키워드 매칭 (<100ms)을 제거한 대가
2. **비결정적**: 같은 질의도 다른 Tool 선택 가능
   - LLM의 확률적 특성
3. **Tool Calling 의존**: llama3.2:1b 지원 필수
   - 모델 변경 시 재테스트 필요

**결론**: 이 프로젝트는 **학습 목적**이므로 성능보다 **확장성과 표준 패턴**을 우선시했습니다.

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

### 새 Tool 추가하기

```python
# 1. tools/document_tools.py에 @tool 데코레이터로 함수 정의
@tool
async def my_new_tool(query: str, session_context: Dict) -> str:
    """Tool 설명 (LLM이 이 설명을 보고 선택)"""
    # 로직 구현
    return "결과"

# 2. AVAILABLE_TOOLS 리스트에 추가
AVAILABLE_TOOLS.append(my_new_tool)

# 끝! Agent가 자동으로 인식
```

### LangSmith 디버깅

1. https://smith.langchain.com → Projects → llmproject-phase2
2. 각 요청의 Agent 노드별 입/출력 확인
3. Tool 선택 과정 추적
4. 에러 발생 시 스택 트레이스 확인

---

## 📚 문서

- **[CLAUDE.md](CLAUDE.md)** - 개발 가이드 (아키텍처, 패턴, 디버깅)
- **[DEPLOY.md](DEPLOY.md)** - 폐쇄망 배포 가이드

---

## 📝 API 예제

### Tool-based Chat

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "계약서에서 금액은 얼마야?"
  }'

# LLM이 search_documents tool을 선택하여 실행
# Response:
{
  "answer": "계약 금액은 5,000만원입니다.\n\n참조 문서:\n- 계약서 3페이지...",
  "intent": null,
  "sources": [],
  "query_log_id": 123
}
```

### 대화 이력 조회

```bash
curl http://localhost:8000/api/chat/history?limit=5
```

---

## ⚡ 성능 특성

### 현재 성능 (llama3.2:1b + Lazy Loading)

- Backend 시작 시간: **3초** (Lazy Init 적용)
- 초기 메모리: **400MB** (FastEmbed 미로드)
- 첫 RAG 호출: **5초** (FastEmbed 로딩 2초 + 검색 3초)
- 이후 RAG 호출: **3초** (FastEmbed 재사용)
- Tool 선택: **2-5초** (LLM 호출)
- 총 응답 시간: **5-10초**

### Lazy Loading 효과

| 항목 | Before | After | 개선율 |
|------|--------|-------|--------|
| 시작 시간 | 15초 | 3초 | 5배 |
| 초기 메모리 | 1.2GB | 400MB | 3배 |
| RAG 미사용 시 메모리 | 1.2GB | 400MB | 3배 |

---

## 🐛 문제 해결

### 컨테이너 상태 확인

```bash
# 전체 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f backend

# 재시작
docker-compose restart backend
```

### 연결 오류

```bash
# PostgreSQL 연결 확인
docker exec postgres psql -U admin -d applicants_db -c "SELECT 1"

# Ollama 연결 확인
docker exec backend curl http://ollama:11434/api/version

# Qdrant 연결 확인
docker exec backend curl http://qdrant:6333/collections
```

### Tool Calling 오류

**증상**: "Tool not found" or "Invalid tool_calls"

**해결**:
```bash
# llama3.2:3b로 업그레이드 (tool calling 안정성 향상)
docker exec ollama ollama pull llama3.2:3b
# .env에서 OLLAMA_MODEL=llama3.2:3b 설정 후 재시작
docker-compose restart backend
```

---

## 📖 학습 리소스

### 이 프로젝트로 배우는 현업 패턴

1. **LangChain Tool Calling**: `@tool` 데코레이터, `bind_tools()`, `ToolNode`
2. **LangGraph ReAct Agent**: StateGraph, 조건부 엣지, 순환 플로우
3. **DDD 설계**: Agent vs Tool 책임 분리
4. **LangSmith 활용**: 자동 추적, 디버깅, 성능 분석
5. **LCEL Chains**: `|` 연산자, `RunnableLambda`, `RunnablePassthrough`
6. **Singleton Pattern**: 모듈 레벨 인스턴스 관리
7. **Lazy Initialization**: `@property` 기반 리소스 최적화
8. **FastAPI + SQLModel**: Async DB 세션, Dependency Injection

### 학습 순서 추천

1. [document_tools.py](backend/app/tools/document_tools.py) - Tool 정의 방법
2. [agent_graph.py](backend/app/graphs/agent_graph.py) - Agent 구성
3. [rag_chain.py](backend/app/chains/rag_chain.py) - Lazy Init 패턴
4. [chat.py](backend/app/api/chat.py) - API 통합
5. LangSmith 대시보드 - 실행 플로우 시각화
6. 새 Tool 추가 실습

---

## 📋 빌드 히스토리

### Phase 전환: Two-tier → Tool-based

**주요 변경사항:**
- ~~`chat_graph.py`~~ 삭제 → `agent_graph.py` (ReAct Agent)
- ~~`query_router.py`~~ 삭제 → LLM Tool Calling
- ~~Intent 테이블~~ 제거 → LLM이 직접 추론
- **Lazy Initialization 패턴 도입** (메모리 최적화)

**해결한 오류:**
1. Import 순환 참조 → Singleton 패턴
2. FastEmbed 캐시 경로 오류 → docker-compose 볼륨 마운트
3. Qdrant Collection 미존재 → `ensure_collection()` 추가
4. 메모리 과다 사용 → `@property` 기반 Lazy Loading

---

## 📝 라이선스

MIT License

---

**LangChain Tool Calling으로 확장 가능한 RAG 시스템 구축 🚀**
