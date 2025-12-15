# LangChain/LangGraph 마이그레이션 계획

## 📋 개요

현재 커스텀 RAG 시스템을 LangChain/LangGraph 기반으로 확장하여 별도 저장소에서 관리합니다.

**목적:**
- 현재 프로젝트: 폐쇄망 배포용 경량 커스텀 RAG (유지)
- 새 프로젝트: LangChain/LangGraph 활용한 고급 기능 구현 (확장)

---

## 🎯 현재 프로젝트 vs 확장 프로젝트

| 구분 | 현재 (Custom RAG) | 확장 (LangChain/LangGraph) |
|------|------------------|---------------------------|
| **목적** | 폐쇄망 배포, 경량화 | 기능 확장, 실험, 프로덕션 고도화 |
| **의존성** | FastAPI, Qdrant, FastEmbed, Ollama | + LangChain, LangGraph, LangSmith |
| **크기** | 백엔드 이미지 ~767MB | ~1.2GB (LangChain 의존성 추가) |
| **장점** | 빠른 배포, 투명성, 제어 가능 | 표준화, 에이전트, 복잡한 워크플로 |
| **적합 환경** | 폐쇄망, 리소스 제약 | 클라우드, 실험 환경 |

---

## 📂 새 저장소 구조

```
llmproject-langchain/
├── README.md                           # 새 프로젝트 개요
├── MIGRATION_FROM_CUSTOM.md            # 커스텀 → LangChain 마이그레이션 가이드
├── LANGCHAIN_ARCHITECTURE.md           # LangChain 아키텍처 설계
├── docker-compose.yml                  # LangChain 전용 컴포즈
├── docker-compose.dev.yml
├── .env.example
├── init.sql                            # 기존 스키마 + 새 테이블 (agent_runs, tool_logs)
│
├── backend/
│   ├── requirements.txt                # + langchain, langgraph, langsmith
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/                     # 기존 모델 유지 + 새 모델
│   │   │   ├── applicant.py
│   │   │   ├── few_shot.py
│   │   │   ├── query_log.py
│   │   │   ├── chat.py
│   │   │   └── agent.py                # ✨ 새로 추가: Agent 실행 이력
│   │   │
│   │   ├── chains/                     # ✨ LangChain Chains
│   │   │   ├── __init__.py
│   │   │   ├── rag_chain.py            # LCEL 기반 RAG 체인
│   │   │   ├── sql_chain.py            # SQL 생성 체인
│   │   │   └── decomposer_chain.py     # Query Decomposition 체인
│   │   │
│   │   ├── graphs/                     # ✨ LangGraph Workflows
│   │   │   ├── __init__.py
│   │   │   ├── chat_graph.py           # 메인 채팅 그래프 (Two-tier → RAG/SQL)
│   │   │   ├── hybrid_graph.py         # 하이브리드 검색 그래프 (RAG + SQL 병렬)
│   │   │   └── fewshot_loop_graph.py   # Few-shot 자동 승격 그래프
│   │   │
│   │   ├── agents/                     # ✨ LangChain Agents
│   │   │   ├── __init__.py
│   │   │   ├── rag_agent.py            # RAG 에이전트
│   │   │   ├── sql_agent.py            # SQL 에이전트 (LangChain SQL Agent)
│   │   │   └── orchestrator_agent.py   # 멀티 에이전트 오케스트레이터
│   │   │
│   │   ├── tools/                      # ✨ LangChain Tools
│   │   │   ├── __init__.py
│   │   │   ├── qdrant_tool.py          # Qdrant 검색 Tool
│   │   │   ├── db_query_tool.py        # DB 쿼리 Tool
│   │   │   ├── intent_check_tool.py    # Intent 테이블 조회 Tool
│   │   │   └── fewshot_retrieve_tool.py # Few-shot 조회 Tool
│   │   │
│   │   ├── services/                   # 기존 서비스 유지 (호환성)
│   │   │   ├── ollama_service.py       # LangChain Ollama 래퍼로 교체
│   │   │   ├── qdrant_service.py       # LangChain Qdrant 래퍼로 교체
│   │   │   └── legacy/                 # 기존 커스텀 서비스 보관
│   │   │       ├── rag_service.py
│   │   │       ├── query_router.py
│   │   │       └── sql_agent.py
│   │   │
│   │   ├── api/                        # API 엔드포인트
│   │   │   ├── chat.py                 # LangGraph 기반으로 재작성
│   │   │   ├── analysis.py             # 기존 유지
│   │   │   ├── upload.py               # 기존 유지
│   │   │   ├── intent.py               # 기존 유지
│   │   │   ├── query_log.py            # 기존 유지
│   │   │   ├── fewshot.py              # 기존 유지
│   │   │   └── agent.py                # ✨ 새로 추가: Agent 실행 모니터링
│   │   │
│   │   └── config/                     # ✨ LangChain 설정
│   │       ├── __init__.py
│   │       ├── langchain_config.py     # LangChain 전역 설정
│   │       └── langsmith_config.py     # LangSmith 추적 설정
│
├── frontend/                           # 기존 프론트엔드 + Agent 모니터링 UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── ApplicantAnalysis.tsx   # 기존 유지
│   │   │   ├── ChatInterface.tsx       # 기존 유지
│   │   │   ├── IntentManagement.tsx    # 기존 유지
│   │   │   ├── QueryLogManagement.tsx  # 기존 유지
│   │   │   ├── FewShotManagement.tsx   # 기존 유지
│   │   │   ├── AgentMonitor.tsx        # ✨ 새로 추가: Agent 실행 모니터링
│   │   │   └── LangGraphVisualization.tsx # ✨ 새로 추가: 그래프 시각화
│   │   └── App.tsx
│
└── docs/                               # 문서
    ├── CHAINS_GUIDE.md                 # LangChain Chains 가이드
    ├── GRAPHS_GUIDE.md                 # LangGraph 워크플로 가이드
    ├── AGENTS_GUIDE.md                 # Agents 가이드
    └── COMPARISON.md                   # 커스텀 vs LangChain 비교
```

---

## 🔄 마이그레이션 전략

### Phase 1: 저장소 설정 및 기본 구조 (1일)

```bash
# 1. 새 저장소 생성
cd ~/projects
git clone <현재-저장소-URL> llmproject-langchain
cd llmproject-langchain

# 2. 원격 저장소 변경
git remote remove origin
git remote add origin <새-저장소-URL>

# 3. 브랜치 전략
git checkout -b main                    # 메인 브랜치
git checkout -b feature/langchain-core  # LangChain 핵심 기능
git checkout -b feature/langgraph       # LangGraph 워크플로
```

**작업 내용:**
- [x] 새 Git 저장소 생성 (GitHub/GitLab)
- [x] 기존 코드 복사
- [x] README.md 작성 (LangChain 버전임을 명시)
- [x] 의존성 추가 (`requirements.txt`)

### Phase 2: LangChain 핵심 통합 (3-4일)

#### 2.1. 의존성 추가

**`backend/requirements.txt` 추가:**
```txt
# 기존 의존성 유지
fastapi==0.115.4
uvicorn==0.32.0
sqlmodel==0.0.22
qdrant-client==1.12.1
fastembed==0.3.6
python-dotenv==1.0.1

# ✨ LangChain 추가
langchain==0.3.9
langchain-community==0.3.8
langchain-core==0.3.21
langgraph==0.2.50
langsmith==0.1.145
langchain-ollama==0.2.0           # Ollama 통합
langchain-qdrant==0.2.0           # Qdrant 통합
```

#### 2.2. LangChain Chains 구현

**목표:** 기존 커스텀 서비스를 LangChain LCEL로 변환

**파일: `backend/app/chains/rag_chain.py`**
```python
"""
LangChain LCEL 기반 RAG Chain
기존 RAGService를 LangChain으로 재구현
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import OllamaLLM
from langchain_qdrant import QdrantVectorStore
from typing import Dict, Any, List

class RAGChain:
    def __init__(self, ollama_base_url: str, qdrant_url: str, collection_name: str):
        # LLM 초기화
        self.llm = OllamaLLM(
            base_url=ollama_base_url,
            model="llama3.2:1b"
        )

        # Qdrant 벡터 스토어 초기화
        from fastembed import TextEmbedding
        embedding_model = TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        )

        self.vectorstore = QdrantVectorStore(
            url=qdrant_url,
            collection_name=collection_name,
            embedding=embedding_model
        )

        # Few-shot 프롬프트 템플릿 (기존과 동일)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 문서 검색 기반 질의응답 AI입니다.

            {few_shot_examples}

            검색된 문서:
            {context}
            """),
            ("human", "{question}")
        ])

        # LCEL Chain 구성
        self.chain = (
            {
                "context": self._format_docs | RunnablePassthrough(),
                "question": RunnablePassthrough(),
                "few_shot_examples": self._get_few_shots
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    def _format_docs(self, docs: List) -> str:
        """검색된 문서를 컨텍스트로 변환"""
        return "\n\n".join([doc.page_content for doc in docs])

    def _get_few_shots(self, session, intent_type: str = "rag_search") -> str:
        """Few-shot 예제 조회 (기존 로직 유지)"""
        from sqlmodel import select
        from app.models.few_shot import FewShot

        few_shots = session.exec(
            select(FewShot)
            .where(FewShot.is_active == True)
            .where(FewShot.intent_type == intent_type)
            .order_by(FewShot.created_at.desc())
        ).all()

        if not few_shots:
            return ""

        examples = []
        for fs in few_shots:
            examples.append(f"질문: {fs.user_query}\n답변: {fs.expected_response}")

        return "예시:\n" + "\n\n".join(examples)

    async def invoke(self, question: str, session, top_k: int = 3) -> Dict[str, Any]:
        """RAG Chain 실행"""
        # 1. Qdrant 검색
        docs = self.vectorstore.similarity_search(question, k=top_k)

        # 2. Chain 실행
        answer = await self.chain.ainvoke({
            "question": question,
            "context": docs,
            "session": session
        })

        # 3. 결과 반환 (기존 형식 유지)
        return {
            "answer": answer,
            "sources": [
                {
                    "text": doc.page_content[:200],
                    "score": doc.metadata.get("score", 0.0),
                    "metadata": doc.metadata
                }
                for doc in docs
            ],
            "has_sources": len(docs) > 0
        }

# 싱글톤
rag_chain = None

def get_rag_chain():
    global rag_chain
    if rag_chain is None:
        import os
        rag_chain = RAGChain(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL"),
            qdrant_url=os.getenv("QDRANT_URL"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "documents")
        )
    return rag_chain
```

**마이그레이션 매핑:**
- `RAGService.answer_question()` → `RAGChain.invoke()`
- 커스텀 프롬프트 → `ChatPromptTemplate`
- 수동 Qdrant 검색 → `QdrantVectorStore.similarity_search()`
- 수동 Few-shot 주입 → LCEL Runnable

#### 2.3. SQL Chain 구현

**파일: `backend/app/chains/sql_chain.py`**
```python
"""
LangChain SQL Agent로 자연어 → SQL 변환
"""
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_ollama import OllamaLLM

class SQLChain:
    def __init__(self, database_url: str, ollama_base_url: str):
        self.llm = OllamaLLM(base_url=ollama_base_url, model="llama3.2:1b")
        self.db = SQLDatabase.from_uri(database_url)

        # LangChain SQL Agent 생성 (기존 커스텀 SQL Agent 대체)
        self.agent = create_sql_agent(
            llm=self.llm,
            db=self.db,
            agent_type="zero-shot-react-description",
            verbose=True
        )

    async def execute_query(self, question: str, session) -> Dict[str, Any]:
        """자연어 질의를 SQL로 변환하여 실행"""
        result = await self.agent.ainvoke({"input": question})

        return {
            "answer": result["output"],
            "sql": result.get("intermediate_steps", []),  # 생성된 SQL
            "results": []
        }
```

### Phase 3: LangGraph 워크플로 구현 (5-7일)

#### 3.1. Two-Tier Intent Classification Graph

**목표:** 기존 `QueryRouter.classify_intent_simple()`을 LangGraph로 변환

**파일: `backend/app/graphs/chat_graph.py`**
```python
"""
LangGraph 기반 채팅 워크플로
Two-Tier Intent Classification + RAG/SQL 라우팅
"""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
from app.chains.rag_chain import get_rag_chain
from app.chains.sql_chain import sql_chain

class ChatState(TypedDict):
    """채팅 상태"""
    query: str
    intent: Literal["rag_search", "sql_query", "general", "unknown"]
    intent_candidates: list[str]
    answer: str
    sources: list
    sql: str
    session: Any

def check_intent_table(state: ChatState) -> ChatState:
    """Tier 1: intents 테이블 키워드 매칭"""
    from app.services.query_router import query_router

    session = state["session"]
    query = state["query"]

    result = query_router._check_intent_table(query, session)

    if isinstance(result, str):  # QueryIntent
        state["intent"] = result
    elif isinstance(result, list):
        state["intent_candidates"] = result
        state["intent"] = "unknown"  # LLM으로 disambiguate 필요
    else:
        state["intent"] = "unknown"

    return state

async def classify_with_llm(state: ChatState) -> ChatState:
    """Tier 2: LLM 기반 Intent 분류"""
    from app.services.query_router import query_router

    intent = await query_router.classify_intent(
        state["query"],
        intent_candidates=state.get("intent_candidates")
    )
    state["intent"] = intent.value
    return state

async def execute_rag(state: ChatState) -> ChatState:
    """RAG Chain 실행"""
    rag_chain = get_rag_chain()
    result = await rag_chain.invoke(state["query"], state["session"])

    state["answer"] = result["answer"]
    state["sources"] = result["sources"]
    return state

async def execute_sql(state: ChatState) -> ChatState:
    """SQL Chain 실행"""
    result = await sql_chain.execute_query(state["query"], state["session"])

    state["answer"] = result["answer"]
    state["sql"] = result["sql"]
    return state

async def execute_general(state: ChatState) -> ChatState:
    """일반 대화"""
    from app.services.ollama_service import ollama_service
    answer = await ollama_service.generate_with_fewshot(
        state["query"],
        state["session"],
        intent_type="general"
    )
    state["answer"] = answer
    return state

def route_by_intent(state: ChatState) -> str:
    """Intent에 따라 다음 노드 결정"""
    intent = state["intent"]

    if intent == "unknown":
        return "classify_llm"
    elif intent == "rag_search":
        return "rag"
    elif intent == "sql_query":
        return "sql"
    else:
        return "general"

# LangGraph 구성
workflow = StateGraph(ChatState)

# 노드 추가
workflow.add_node("check_intent", check_intent_table)
workflow.add_node("classify_llm", classify_with_llm)
workflow.add_node("rag", execute_rag)
workflow.add_node("sql", execute_sql)
workflow.add_node("general", execute_general)

# 엣지 추가
workflow.set_entry_point("check_intent")
workflow.add_conditional_edges(
    "check_intent",
    route_by_intent,
    {
        "classify_llm": "classify_llm",
        "rag": "rag",
        "sql": "sql",
        "general": "general"
    }
)
workflow.add_conditional_edges(
    "classify_llm",
    route_by_intent,
    {
        "rag": "rag",
        "sql": "sql",
        "general": "general"
    }
)
workflow.add_edge("rag", END)
workflow.add_edge("sql", END)
workflow.add_edge("general", END)

# 컴파일
chat_graph = workflow.compile()
```

**사용 예시 (API에서):**
```python
# backend/app/api/chat.py
from app.graphs.chat_graph import chat_graph

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, session: Session = Depends(get_session)):
    result = await chat_graph.ainvoke({
        "query": request.query,
        "intent": "unknown",
        "intent_candidates": [],
        "answer": "",
        "sources": [],
        "sql": "",
        "session": session
    })

    # query_log 저장 (기존과 동일)
    query_log = QueryLog(
        query_text=request.query,
        detected_intent=result["intent"],
        response=result["answer"]
    )
    session.add(query_log)
    session.commit()

    return ChatResponse(
        answer=result["answer"],
        intent=result["intent"],
        sources=result.get("sources", []),
        sql=result.get("sql")
    )
```

#### 3.2. Hybrid Search Graph (RAG + SQL 병렬 실행)

**파일: `backend/app/graphs/hybrid_graph.py`**
```python
"""
하이브리드 검색: RAG와 SQL을 병렬로 실행하고 결과 병합
"""
from langgraph.graph import StateGraph, END

class HybridState(TypedDict):
    query: str
    unstructured_query: str
    structured_query: str
    rag_answer: str
    sql_answer: str
    final_answer: str
    sources: list
    session: Any

async def decompose_query(state: HybridState) -> HybridState:
    """질의 분해"""
    from app.services.query_decomposer import query_decomposer

    result = await query_decomposer.decompose_query(state["query"])
    state["unstructured_query"] = result.get("unstructured_query", "")
    state["structured_query"] = result.get("structured_query", "")
    return state

async def execute_rag_parallel(state: HybridState) -> HybridState:
    """RAG 검색 (병렬)"""
    if state["unstructured_query"]:
        rag_chain = get_rag_chain()
        result = await rag_chain.invoke(state["unstructured_query"], state["session"])
        state["rag_answer"] = result["answer"]
        state["sources"] = result["sources"]
    return state

async def execute_sql_parallel(state: HybridState) -> HybridState:
    """SQL 쿼리 (병렬)"""
    if state["structured_query"]:
        result = await sql_chain.execute_query(state["structured_query"], state["session"])
        state["sql_answer"] = result["answer"]
    return state

async def merge_results(state: HybridState) -> HybridState:
    """결과 병합"""
    parts = []
    if state.get("rag_answer"):
        parts.append(state["rag_answer"])
    if state.get("sql_answer"):
        parts.append(state["sql_answer"])

    state["final_answer"] = "\n\n".join(parts)
    return state

# 그래프 구성
workflow = StateGraph(HybridState)
workflow.add_node("decompose", decompose_query)
workflow.add_node("rag", execute_rag_parallel)
workflow.add_node("sql", execute_sql_parallel)
workflow.add_node("merge", merge_results)

workflow.set_entry_point("decompose")
workflow.add_edge("decompose", "rag")
workflow.add_edge("decompose", "sql")  # 병렬 실행
workflow.add_edge("rag", "merge")
workflow.add_edge("sql", "merge")
workflow.add_edge("merge", END)

hybrid_graph = workflow.compile()
```

### Phase 4: LangSmith 통합 (1-2일)

**추적 설정:**
```python
# backend/app/config/langsmith_config.py
import os
from langsmith import Client

def setup_langsmith():
    """LangSmith 추적 활성화"""
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
    os.environ["LANGCHAIN_PROJECT"] = "llmproject-langchain"

# main.py에서 호출
from app.config.langsmith_config import setup_langsmith
setup_langsmith()
```

---

## 🚀 배포 전략

### 개발 환경

**기존과 동일하게 docker-compose.dev.yml 사용:**
```yaml
# docker-compose.dev.yml (LangChain 버전)
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      # 기존 환경 변수 유지
      DATABASE_URL: postgresql://admin:admin123@postgres:5432/applicants_db
      OLLAMA_BASE_URL: http://ollama:11434
      QDRANT_URL: http://qdrant:6333

      # ✨ LangSmith 추가
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY}
      LANGCHAIN_TRACING_V2: "true"
    volumes:
      - ./backend/app:/app/app
```

### 프로덕션 배포

**LangChain 버전은 폐쇄망이 아닌 클라우드 환경 권장:**
- Docker Compose (단일 서버)
- Kubernetes (멀티 서버, 오토스케일링)
- LangSmith 추적 활성화

---

## 📊 기대 효과

### 1. 개발 생산성

| 작업 | 커스텀 RAG | LangChain/LangGraph |
|------|-----------|---------------------|
| RAG Chain 구현 | 200줄 (수동) | 50줄 (LCEL) |
| SQL Agent 구현 | 300줄 (패턴 매칭) | 10줄 (내장 Agent) |
| 워크플로 구현 | if/else 중첩 | 그래프 시각화 |
| 디버깅 | print() | LangSmith 추적 |

### 2. 기능 확장성

**LangChain/LangGraph로 가능한 기능:**
- ✅ Multi-Agent Collaboration (여러 에이전트 협업)
- ✅ Human-in-the-Loop (사람 개입 워크플로)
- ✅ Streaming Responses (실시간 응답 스트리밍)
- ✅ Memory Management (대화 이력 관리)
- ✅ Tool Calling (외부 API 호출)

### 3. 모니터링

**LangSmith 대시보드:**
- Chain 실행 추적
- 토큰 사용량 분석
- 오류 디버깅
- A/B 테스트

---

## ⚖️ 트레이드오프

| 측면 | 커스텀 RAG (현재) | LangChain/LangGraph (확장) |
|------|------------------|---------------------------|
| **학습 곡선** | 낮음 (직접 구현) | 중간 (프레임워크 학습) |
| **제어 가능성** | 높음 (모든 코드 직접) | 중간 (추상화됨) |
| **디버깅** | 쉬움 (직접 작성) | 복잡 (프레임워크 레이어) |
| **의존성** | 적음 | 많음 (LangChain 생태계) |
| **커뮤니티** | 없음 | 활발 (LangChain 커뮤니티) |
| **폐쇄망 배포** | 쉬움 | 어려움 (의존성 많음) |

---

## 🎯 마이그레이션 체크리스트

### Phase 1: 준비 (1일)
- [ ] 새 Git 저장소 생성
- [ ] 기존 코드 복사
- [ ] README.md 작성
- [ ] requirements.txt에 LangChain 의존성 추가
- [ ] 로컬 환경에서 기존 기능 동작 확인

### Phase 2: LangChain Chains (3-4일)
- [ ] `chains/rag_chain.py` 구현
- [ ] `chains/sql_chain.py` 구현
- [ ] `chains/decomposer_chain.py` 구현
- [ ] 기존 API에서 Chains 호출 테스트
- [ ] Few-shot 통합 확인

### Phase 3: LangGraph Workflows (5-7일)
- [ ] `graphs/chat_graph.py` 구현 (Two-Tier)
- [ ] `graphs/hybrid_graph.py` 구현 (병렬 실행)
- [ ] API 엔드포인트 재작성
- [ ] 통합 테스트

### Phase 4: LangSmith (1-2일)
- [ ] LangSmith 계정 생성
- [ ] 추적 설정
- [ ] 대시보드 확인

### Phase 5: 문서화 (2-3일)
- [ ] LANGCHAIN_ARCHITECTURE.md 작성
- [ ] CHAINS_GUIDE.md 작성
- [ ] GRAPHS_GUIDE.md 작성
- [ ] COMPARISON.md 작성 (커스텀 vs LangChain)

### Phase 6: 배포 (1-2일)
- [ ] docker-compose.yml 테스트
- [ ] 프로덕션 환경 배포
- [ ] 모니터링 설정

**총 예상 기간: 2-3주**

---

## 📚 다음 단계

1. **새 저장소 URL 공유해주시면** 즉시 시작 가능합니다
2. **Phase별로 PR 생성** (feature/langchain-core → main)
3. **기존 커스텀 RAG와 병행 개발** (양쪽 모두 유지)

궁금하신 점이나 수정이 필요한 부분이 있으면 말씀해주세요!
