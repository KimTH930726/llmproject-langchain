# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tool-based Agent RAG 시스템** - 학습 목적의 현업 표준 패턴 구현

LangChain Tool Calling + LangGraph를 활용한 확장 가능한 RAG (Retrieval-Augmented Generation) 시스템입니다.

**핵심 아키텍처:**
- LLM이 사용자 질의를 분석하여 적절한 Tool을 자동 선택
- ReAct Agent 패턴 (Reasoning + Acting)
- DDD(Domain-Driven Design) 원칙에 따른 책임 분리
- Lazy Initialization을 통한 메모리 효율화
- LangSmith 통합으로 모든 실행 자동 추적

**배포 환경:** 폐쇄망 서버 (PostgreSQL, Ollama, Qdrant 실행 중)

**참고 문서:**
- [README.md](README.md) - 프로젝트 개요 및 빠른 시작
- [DEPLOY.md](DEPLOY.md) - 폐쇄망 배포 가이드

---

## Tech Stack

### Backend
- **Framework**: FastAPI, SQLModel
- **LLM**: Ollama (llama3.2:1b with Tool Calling)
- **Vector DB**: Qdrant + FastEmbed (ONNX, 778MB)
- **DB**: PostgreSQL 16 (Query Logs, 지원자 정보)
- **Embedding**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768차원)

### LangChain Ecosystem
- **LangChain**: 0.3.9 (Tool Calling, LCEL Chains, Prompts)
- **LangGraph**: 0.2.50 (ReAct Agent, ToolNode, StateGraph)
- **LangSmith**: 0.1.145 (자동 추적, 디버깅, 성능 분석)

### Frontend
- **Framework**: React 19, TypeScript
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 4

---

## Development Commands

### 로컬 개발 (Docker 전체 스택)

```bash
# 전체 스택 시작 (PostgreSQL, Ollama, Qdrant, Backend, Frontend)
docker-compose -f docker-compose.dev.yml up -d

# Ollama 모델 다운로드 (최초 1회)
docker exec -it ollama ollama pull llama3.2:1b

# 로그 확인
docker-compose logs -f backend

# 백엔드 재시작 (코드 변경 후)
docker-compose restart backend

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

**참고:** 폐쇄망 배포는 [DEPLOY.md](DEPLOY.md) 참조

---

## Architecture

### 핵심 아키텍처 패턴

#### 1. ReAct Agent Pattern ([agent_graph.py](backend/app/graphs/agent_graph.py))

현업 표준 패턴: LLM이 Tool을 선택하고 실행하는 순환 구조

```
사용자 질의 → Agent 노드 (Tool 선택) → Tool 노드 (실행) → Agent 노드 (결과 해석) → 반복
```

**핵심 코드:**
```python
# backend/app/graphs/agent_graph.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# 1. Agent 노드: LLM이 Tool 선택
async def agent_node(state: AgentState):
    llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}

# 2. StateGraph 구성
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(AVAILABLE_TOOLS))

# 3. 조건부 라우팅
workflow.add_conditional_edges(
    "agent",
    should_continue,  # Tool 호출 필요? → "tools" or "end"
    {"tools": "tools", "end": END}
)

# 4. Tool 실행 후 다시 Agent로
workflow.add_edge("tools", "agent")
```

**왜 이 패턴?**
- LangGraph 공식 추천 패턴
- `ToolNode`: Tool 실행 + 에러 핸들링 자동화
- `should_continue`: LLM 응답에 `tool_calls` 있는지 자동 판단
- 가장 많은 레퍼런스 (tutorials, cookbooks)

#### 2. DDD 기반 책임 분리 패턴

**Agent 도메인 (graphs/agent_graph.py):**
- "어떻게 학습하는가" → Few-shot 프롬프트 주입
- "어떤 Tool을 선택하는가" → Tool Calling

**Tool 도메인 (tools/document_tools.py):**
- "무엇을 하는가" → 순수 기능 실행
- DB/API 호출은 Tool 내부에서 처리

**예시: Few-shot은 Agent 책임**
```python
# ❌ 안티패턴: Tool 내부에서 Few-shot 로드
@tool
def rag_tool(query: str):
    few_shots = get_few_shots()  # Tool이 학습 방법까지 알아야 함
    # ...

# ✅ 올바른 패턴: Agent 레벨에서 주입
def build_system_prompt_with_fewshots(session):
    few_shots = get_few_shots()
    return f"시스템 프롬프트\n\n예시:\n{few_shots}"

# Agent 노드에서 사용
system_prompt = build_system_prompt_with_fewshots(session)
messages = [SystemMessage(content=system_prompt)] + state["messages"]
```

**장점:**
- Tool은 독립적 (DB Session 불필요)
- Agent는 학습 로직만 관리
- 같은 Tool을 다른 Agent에서 다른 방식으로 사용 가능

#### 3. LangChain Tool 정의 패턴 ([document_tools.py](backend/app/tools/document_tools.py))

```python
from langchain_core.tools import tool

@tool
async def search_documents(query: str, session_context: Dict[str, Any]) -> str:
    """
    업로드된 문서에서 관련 정보를 검색합니다.

    계약서, 제안서, 기술 문서 등에서 특정 내용을 찾을 때 사용하세요.

    Args:
        query: 검색할 질문
        session_context: DB 세션을 포함한 컨텍스트

    Returns:
        검색 결과 및 관련 문서 정보
    """
    # RAGChain 호출
    rag_chain = get_rag_chain()
    result = await rag_chain.invoke(query, session_context.get("session"))

    # Tool은 문자열 반환 (LangChain 규약)
    return result["answer"]

# Tool 목록 (Agent가 사용)
AVAILABLE_TOOLS = [search_documents, query_database, general_conversation]
```

**Tool 작성 규칙:**
1. `@tool` 데코레이터 사용
2. **Docstring 필수**: LLM이 이 설명을 보고 Tool 선택
3. **문자열 반환**: LangChain 표준 (dict/object 아님)
4. **session_context 패턴**: DB 세션을 Tool에 전달

#### 4. Lazy Initialization Pattern (메모리 최적화)

모든 무거운 리소스(FastEmbed, Qdrant Client, VectorStore)는 Lazy Loading:

```python
# backend/app/chains/rag_chain.py
class RAGChain:
    def __init__(self):
        # 즉시 초기화하지 않음
        self._embedding = None
        self._qdrant_client = None
        self._vectorstore = None

    @property
    def embedding(self):
        """Lazy load FastEmbed model (778MB)"""
        if self._embedding is None:
            self._embedding = TextEmbedding(
                model_name=self.embedding_model_name,
                cache_dir=self.fastembed_cache
            )
        return self._embedding

    @property
    def vectorstore(self):
        """Lazy load Qdrant vector store"""
        if self._vectorstore is None:
            self._vectorstore = QdrantVectorStore(
                client=self.qdrant_client,
                collection_name=self.collection_name,
                embedding=self.embedding
            )
        return self._vectorstore
```

**효과:**
- Backend 시작 시간: 15초 → 3초
- 초기 메모리: 1.2GB → 400MB
- RAG 미사용 시 임베딩 모델 로드 안 됨

#### 5. Singleton Service Pattern

모든 서비스는 모듈 레벨 싱글톤 (FastAPI 라이프사이클 독립):

```python
# backend/app/graphs/agent_graph.py
_agent_graph_instance = None

def get_agent_graph():
    global _agent_graph_instance
    if _agent_graph_instance is None:
        _agent_graph_instance = create_agent_graph()
    return _agent_graph_instance

# backend/app/api/chat.py
from app.graphs.agent_graph import get_agent_graph

agent = get_agent_graph()  # import만으로 재사용
```

#### 6. LangGraph State Management Pattern

**TypedDict 기반 상태 정의:**
```python
from typing import TypedDict, Annotated, Sequence
from operator import add
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # Annotated[Sequence[BaseMessage], add]: 메시지를 누적 추가
    messages: Annotated[Sequence[BaseMessage], add]
    session_context: dict  # Tool에 전달할 런타임 컨텍스트
```

**왜 Annotated[..., add]?**
- LangGraph는 상태 업데이트를 "병합"함
- `add` 연산자: 기존 messages에 새 메시지 추가 (덮어쓰기 X)
- 대화 이력 자동 관리

#### 7. LCEL Chain Pattern ([rag_chain.py](backend/app/chains/rag_chain.py))

LangChain Expression Language로 파이프라인 구성:

```python
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

self.chain = (
    {
        "context": RunnableLambda(self._format_docs),     # 문서 포맷팅
        "question": RunnablePassthrough(),                 # 질문 그대로 전달
        "few_shot_examples": RunnableLambda(lambda x: "") # 기본값
    }
    | self.prompt     # ChatPromptTemplate
    | self.llm        # OllamaLLM
    | StrOutputParser()  # 문자열 추출
)

# 사용
answer = await self.chain.ainvoke({"docs": docs, "question": query})
```

**LCEL 장점:**
- `|` 연산자로 직관적 체이닝
- `ainvoke()`: Async 기본 지원
- LangSmith 자동 추적

---

### 데이터베이스 스키마 (PostgreSQL)

**핵심 테이블:**
- `applicant_info`: 지원자 정보 (읽기 전용, CRUD 없음)
- `query_logs`: 모든 질의 자동 저장 (Few-shot 학습 소스)

**제거된 테이블 (Tool-based로 전환):**
- ~~`intents`~~: 키워드 → intent_type 매핑 (불필요)
- ~~`few_shots`~~: Few-shot 예제 (query_logs로 대체)
- ~~`few_shot_audit`~~: 변경 이력 (불필요)

상세 스키마: [init.sql](init.sql)

---

### 디렉토리 구조

```
backend/app/
├── tools/                  # LangChain Tools (핵심!)
│   └── document_tools.py   # search_documents, query_database, general_conversation
├── graphs/                 # LangGraph 워크플로
│   └── agent_graph.py      # ReAct Agent (agent ↔ tools)
├── chains/                 # LangChain LCEL Chains
│   └── rag_chain.py        # RAG Chain (Qdrant + Ollama, Lazy Init)
├── services/               # 비즈니스 로직 (Helper)
│   ├── sql_agent.py        # NL→SQL 변환
│   ├── ollama_service.py   # Ollama API 래퍼
│   └── qdrant_service.py   # Qdrant 연동 (Lazy Init)
├── api/                    # FastAPI 엔드포인트
│   ├── chat.py             # Tool-based Agent API
│   ├── upload.py           # 문서 업로드
│   ├── analysis.py         # 지원자 분석
│   └── query_log.py        # 대화 이력
├── models/                 # SQLModel 데이터 모델
├── _deprecated/            # 제거된 코드 (백업)
│   ├── chat_graph.py       # Two-tier Intent Classification (삭제됨)
│   ├── query_router.py     # Intent 라우팅 (삭제됨)
│   ├── intent.py           # Intent CRUD API (삭제됨)
│   └── few_shot.py         # Intent, FewShot 모델 (삭제됨)
└── main.py                 # FastAPI 앱
```

---

## Environment Variables

**필수 (.env):**
```bash
# DB
DATABASE_URL=postgresql://admin:admin123@postgres:5432/applicants_db

# LLM
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b

# Vector DB
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=documents
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
FASTEMBED_CACHE_PATH=/app/fastembed_cache

# LangSmith (필수!)
LANGCHAIN_API_KEY=lsv2_...  # https://smith.langchain.com에서 발급
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=llmproject-phase2
```

---

## Development Workflow

### 코드 변경

```bash
# Hot reload (docker-compose.dev.yml 사용 시 자동 반영)
# backend/app/ 디렉토리는 볼륨 마운트됨

# 환경 변수 변경: 재시작만
docker-compose restart backend

# 의존성 변경 (requirements.txt): 재빌드
docker-compose up -d --build backend
```

### API 테스트

- API 문서: http://localhost:8000/docs
- LangSmith 추적: https://smith.langchain.com → llmproject-phase2

### 새 Tool 추가 (핵심 워크플로)

```python
# 1. tools/document_tools.py에 @tool 함수 추가
@tool
async def new_feature_tool(query: str, session_context: Dict) -> str:
    """
    새 기능 설명 (LLM이 읽음!)

    사용 시나리오를 명확히 작성하세요.
    """
    # 로직 구현
    return "결과 문자열"

# 2. AVAILABLE_TOOLS에 추가
AVAILABLE_TOOLS.append(new_feature_tool)

# 끝! Agent가 자동으로 인식
```

### LangSmith 디버깅

1. **추적 확인**: https://smith.langchain.com → llmproject-phase2
2. **Agent 실행 보기**: Run 클릭 → agent_node → tool_node 플로우 확인
3. **Tool 선택 이유**: LLM의 reasoning (tool_calls 필드)
4. **에러 추적**: 실패한 노드에서 스택 트레이스 확인

---

## Adding Features

### 새 Tool 추가 (상세 가이드)

**Step 1: Tool 함수 작성**
```python
# backend/app/tools/document_tools.py
@tool
async def analyze_sentiment(text: str, session_context: Dict) -> str:
    """
    텍스트의 감정을 분석합니다.

    긍정/부정/중립을 판단하고 이유를 설명합니다.

    Args:
        text: 분석할 텍스트
        session_context: 컨텍스트

    Returns:
        감정 분석 결과
    """
    # Ollama 호출
    ollama = session_context.get("ollama_service")
    result = await ollama.generate(
        prompt=f"다음 텍스트의 감정을 분석하세요:\n{text}",
        system_prompt="긍정/부정/중립 중 하나로 판단하고 이유를 설명하세요."
    )

    return result["response"]
```

**Step 2: AVAILABLE_TOOLS에 등록**
```python
AVAILABLE_TOOLS = [
    search_documents,
    query_database,
    general_conversation,
    analyze_sentiment  # 추가!
]
```

**Step 3: 테스트**
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "이 계약서의 분위기는 어때?"}'

# LLM이 analyze_sentiment tool을 자동 선택!
```

**주의사항:**
- Docstring이 LLM이 보는 유일한 가이드!
- 사용 시나리오를 명확히 작성
- session_context는 표준 패턴 (DB, services 전달용)

---

## Troubleshooting

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

**원인 1**: Ollama llama3.2:1b가 tool calling 지원 안 함
```bash
# 모델 확인
docker exec ollama ollama list

# 3b로 변경 (정확도 향상)
OLLAMA_MODEL=llama3.2:3b docker-compose restart backend
```

**원인 2**: Tool docstring 누락
```python
# ❌ 이렇게 하면 LLM이 Tool을 이해 못함
@tool
def my_tool(query):
    return "result"

# ✅ Docstring 필수
@tool
def my_tool(query: str) -> str:
    """명확한 설명"""
    return "result"
```

### LangSmith 추적 안됨

**체크리스트:**
1. `.env`에서 `LANGCHAIN_TRACING_V2=true` 확인
2. `LANGCHAIN_API_KEY` 유효성 (https://smith.langchain.com/settings)
3. Backend 로그에서 "LangSmith tracing enabled" 메시지 확인

**비활성화 방법:**
```bash
LANGCHAIN_TRACING_V2=false docker-compose restart backend
```

### Lazy Loading 관련 오류

**증상**: "FastEmbed model not loaded" or "Qdrant client not initialized"

**원인**: Lazy property 접근 전에 직접 private 변수 사용
```python
# ❌ 잘못된 접근
rag_chain._embedding  # None일 수 있음

# ✅ 올바른 접근
rag_chain.embedding   # @property를 통해 lazy load
```

---

## Important Constraints

- **Read-Only Applicant DB**: `applicant_info` 테이블은 읽기 전용
- **No Intent Tables**: Tool-based 전환으로 intents, few_shots 테이블 제거됨
- **Tool Returns String**: LangChain 규약 (dict 반환 X)
- **Korean-Only**: 모든 프롬프트 한국어
- **Tool Calling Required**: llama3.2:1b 이상 필요 (function calling 지원)
- **LangSmith Dependency**: 개발 환경에서 LangSmith API 키 필수
- **Lazy Loading**: 무거운 리소스는 첫 사용 시 로드 (FastEmbed, Qdrant)

---

## Quick Reference

### 자주 사용하는 명령어

```bash
# 개발 환경 시작/중지
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml down

# 로그 확인
docker-compose logs -f backend

# DB 접속
docker exec -it postgres psql -U admin -d applicants_db

# Ollama 테스트
docker exec backend curl -X POST http://ollama:11434/api/generate \
  -d '{"model":"llama3.2:1b","prompt":"안녕하세요","stream":false}'

# 컨테이너 상태 확인
docker-compose ps
```

### 디버깅 체크리스트

1. **Tool 선택 안됨**: Docstring 명확한지 확인, LangSmith에서 reasoning 확인
2. **LLM 응답 없음**: `docker logs ollama` → 모델 다운로드 확인
3. **RAG 답변 부정확**: Few-shot 예제 부족, Qdrant 문서 확인
4. **DB 연결 실패**: `.env` `DATABASE_URL` 확인
5. **Tool Calling 실패**: llama3.2:1b 지원 확인, 3b로 변경 고려
6. **메모리 부족**: Lazy loading 제대로 동작하는지 확인
7. **시작 시간 느림**: FastEmbed 캐시 경로 확인

---

## Key Request Flow

### Tool-based Chat 요청 플로우

```
[POST /api/chat/] {"query": "계약서에서 금액은?"}
    ↓
[chat.py:44] get_agent_graph().ainvoke({messages, session_context})
    ↓
[agent_graph.py:90] agent_node(state)
    ├─ Few-shot 프롬프트 생성 (query_logs에서 조회)
    ├─ System Message 주입
    ├─ llm.bind_tools(AVAILABLE_TOOLS)
    └─ LLM 호출 → Tool 선택 (search_documents)
    ↓
[agent_graph.py:128] should_continue(state)
    └─ last_message.tool_calls 존재 → "tools"
    ↓
[ToolNode] search_documents 자동 실행
    ├─ [document_tools.py:16] RAGChain.invoke(query)
    │   ├─ [rag_chain.py:98] vectorstore.similarity_search (Lazy Load)
    │   │   └─ [rag_chain.py:81] embedding 첫 호출 시 FastEmbed 로드
    │   ├─ LCEL Chain 실행 (context | prompt | llm | parser)
    │   └─ return {"answer": "...", "sources": [...]}
    └─ ToolMessage 생성 (결과 포함)
    ↓
[agent_graph.py] tools → agent (엣지)
    ↓
[agent_graph.py:90] agent_node(state)  # 다시 호출
    ├─ messages에 ToolMessage 포함
    ├─ LLM이 Tool 결과 보고 최종 답변 생성
    └─ AIMessage (tool_calls 없음)
    ↓
[agent_graph.py:128] should_continue(state)
    └─ tool_calls 없음 → "end"
    ↓
[chat.py:60] 최종 AIMessage 추출
    ↓
[chat.py:66] QueryLog 저장 (query_text, response)
    ↓
[chat.py:74] ChatResponse 반환
```

**핵심 경로 파일:**
- [chat.py](backend/app/api/chat.py) - API 엔드포인트
- [agent_graph.py](backend/app/graphs/agent_graph.py) - Agent 워크플로
- [document_tools.py](backend/app/tools/document_tools.py) - Tool 정의
- [rag_chain.py](backend/app/chains/rag_chain.py) - RAG 구현 (Lazy Init)

**LangSmith 추적:**
- 각 노드 실행 시간
- LLM의 tool 선택 reasoning
- Tool 입/출력
- 최종 답변 생성 과정

---

## Performance Characteristics

**현재 성능 (llama3.2:1b + Lazy Loading):**
- Backend 시작 시간: **3초** (Lazy Init 적용)
- 초기 메모리: **400MB** (FastEmbed 미로드)
- 첫 RAG 호출: **5초** (FastEmbed 로딩 2초 + 검색 3초)
- 이후 RAG 호출: **3초** (FastEmbed 재사용)
- Tool 선택: **2-5초** (LLM 호출)
- 총 응답 시간: **5-10초**

**Lazy Loading 효과:**
| 항목 | Before | After | 개선율 |
|------|--------|-------|--------|
| 시작 시간 | 15초 | 3초 | 5배 |
| 초기 메모리 | 1.2GB | 400MB | 3배 |
| RAG 미사용 시 메모리 | 1.2GB | 400MB | 3배 |

**최적화 가능성:**
- llama3.2:3b 사용 (정확도 향상, 속도 유사)
- Few-shot 예제 추가 (Tool 선택 정확도 향상)
- Tool 내부 캐싱 (RAG 결과 캐싱)
- FastEmbed Warm-up (startup event에서 미리 로드)

---

## Build History & Issues

### Phase 전환: Two-tier → Tool-based

**변경 사항:**
1. ~~`chat_graph.py`~~ 삭제 → `agent_graph.py` (ReAct Agent)
2. ~~`query_router.py`~~ 삭제 → LLM Tool Calling
3. ~~Intent 테이블~~ 제거 → LLM이 직접 추론
4. Lazy Initialization 패턴 도입 (메모리 최적화)

**발생한 주요 오류:**

#### 1. Import 순환 참조
```
ImportError: cannot import name 'get_chat_graph' from partially initialized module
```
**해결**: Singleton 패턴 + 지연 import

#### 2. FastEmbed 캐시 경로 오류
```
FileNotFoundError: /app/fastembed_cache
```
**해결**: docker-compose.dev.yml에 볼륨 마운트 추가

#### 3. Qdrant Collection 미존재
```
UnexpectedResponse: Collection 'documents' does not exist
```
**해결**: `ensure_collection()` 메서드 추가

#### 4. Lazy Loading 전 메모리 과다 사용
```
Backend 시작 15초 소요, 1.2GB 메모리 사용
```
**해결**: `@property` 기반 Lazy Initialization 적용

---

## 학습 포인트

이 프로젝트를 통해 학습할 수 있는 현업 패턴:

1. **LangChain Tool Calling**: `@tool` 데코레이터, `bind_tools()`, `ToolNode`
2. **LangGraph ReAct Agent**: StateGraph, 조건부 엣지, 순환 플로우
3. **DDD 설계**: Agent vs Tool 책임 분리
4. **LangSmith 활용**: 자동 추적, 디버깅, 성능 분석
5. **LCEL Chains**: `|` 연산자, `RunnableLambda`, `RunnablePassthrough`
6. **Singleton Pattern**: 모듈 레벨 인스턴스 관리
7. **Lazy Initialization**: `@property` 기반 리소스 최적화
8. **FastAPI + SQLModel**: Async DB 세션, Dependency Injection

**학습 순서 추천:**
1. [document_tools.py](backend/app/tools/document_tools.py) - Tool 정의 방법
2. [agent_graph.py](backend/app/graphs/agent_graph.py) - Agent 구성
3. [rag_chain.py](backend/app/chains/rag_chain.py) - Lazy Init 패턴
4. [chat.py](backend/app/api/chat.py) - API 통합
5. LangSmith 대시보드 - 실행 플로우 시각화
6. 새 Tool 추가 실습

---

**현업 표준 패턴으로 확장 가능한 RAG 시스템 구축 완료! 🎓🚀**
