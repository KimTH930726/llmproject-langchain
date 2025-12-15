# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

채용 지원자 자기소개서 분석 및 RAG 기반 문서 검색 시스템

**Phase 2 마이그레이션 상태:**
- Phase 1 (커스텀 RAG) → Phase 2 (LangChain/LangGraph) 전환 중
- Phase 2 Chains/Graphs 우선 사용, Phase 1 Services는 fallback 또는 미구현 기능용
- 100% DB 스키마 호환성 유지 (PostgreSQL, Qdrant)

**핵심 기능:**
1. 지원자 분석 (요약, 키워드 추출, 면접 질문 생성)
2. RAG 문서 검색 (PDF/DOCX/TXT/XLSX 업로드 → Qdrant 벡터 DB → LLM 답변)
   - **Phase 2**: LangChain LCEL RAG Chain (200줄 → 50줄)
   - **Phase 2**: LangGraph ChatGraph (Two-Tier Intent Classification 시각화)
3. 자연어 SQL 변환 (질의 → SQL → DB 조회 → 결과 해석)
   - **Phase 1**: 패턴 매칭 SQL Agent (Phase 2: LangChain SQL Agent 예정)
4. Intent & Few-shot 학습 (키워드 매칭 + LLM 분류, 질의 로그 → Few-shot 예제)
5. Multi-Stage RAG (Query Decomposition + Relevance Analysis)
   - **Phase 1**: 커스텀 구현 (Phase 2 마이그레이션 예정)

**배포 환경:** 폐쇄망 서버 (PostgreSQL, Ollama, Qdrant가 이미 실행 중)

**상세 문서:**
- [README.md](README.md) - 프로젝트 개요 및 빠른 시작
- [DEPLOY.md](DEPLOY.md) - 폐쇄망 배포 가이드

## Tech Stack

### Phase 1에서 유지
- **Backend:** FastAPI, SQLModel, Qdrant, FastEmbed (ONNX-based, 778MB vs sentence-transformers 7.97GB)
- **Frontend:** React 19, TypeScript, Vite 7, Tailwind CSS 4
- **LLM:** Ollama (llama3.2:1b)
- **DB:** PostgreSQL 16 (지원자 정보, Intent, Query Logs, Few-shots)
- **Vector DB:** Qdrant (문서 임베딩)
- **Embedding Model:** `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (한국어 지원, 768차원)

### Phase 2에서 추가
- **LangChain:** 0.3.9 (LCEL Chains, PromptTemplate, OutputParsers)
- **LangGraph:** 0.2.50 (StateMachine 워크플로, 시각화)
- **LangSmith:** 0.1.145 (추적, 모니터링, 디버깅)
- **LangChain Integrations:** langchain-ollama, langchain-qdrant

**의존성 크기:** Phase 1 (767MB) → Phase 2 (~1.2GB)

## Development Commands

### 로컬 개발 (Docker 전체 스택)
```bash
# 전체 스택 시작 (PostgreSQL, Ollama, Qdrant 포함)
docker-compose -f docker-compose.dev.yml up -d

# Ollama 모델 다운로드 (최초 1회)
docker exec -it ollama ollama pull llama3.2:1b

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f backend

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

**참고:** 폐쇄망 배포는 [DEPLOY.md](DEPLOY.md) 참조 (FastEmbed 모델 다운로드, Docker 이미지 전송 등)

## Architecture

### 핵심 아키텍처 패턴

#### 1. Two-Tier Intent Classification ([query_router.py](backend/app/services/query_router.py))
질의를 3가지 유형으로 분류 (rag_search, sql_query, general):
- **Tier 1 (Fast)**: `intents` 테이블에서 키워드 매칭 (PostgreSQL `LIKE` 쿼리)
  - 1개 매칭 → 즉시 반환
  - 2+ 매칭 → LLM에 후보 전달하여 disambiguation
  - 0개 매칭 → Tier 2로 fallback
- **Tier 2 (Flexible)**: LLM 기반 분류 (Ollama llama3.2:1b)

**핵심 코드:**
```python
# backend/app/services/query_router.py
async def classify_intent_simple(self, query: str, session: Optional[Session]) -> QueryIntent:
    # 1. intents 테이블 키워드 매칭
    result = self._check_intent_table(query, session)
    if isinstance(result, QueryIntent):
        return result  # 1개만 매칭
    # 2. LLM 기반 분류 (fallback)
    return await self.classify_intent(query, intent_candidates=result)
```

#### 2. Few-Shot Integration Pattern
모든 서비스가 `_get_active_fewshots(session, intent_type)` 메서드를 구현하여 활성 예제를 프롬프트에 주입:
- [rag_service.py](backend/app/services/rag_service.py): RAG 검색 답변 개선
- [sql_agent.py](backend/app/services/sql_agent.py): SQL 쿼리 생성 개선
- [ollama_service.py](backend/app/services/ollama_service.py): 일반 대화 품질 개선

**표준 메서드 시그니처:**
```python
def _get_active_fewshots(self, session: Session, intent_type: str) -> List[FewShot]:
    """모든 서비스가 이 시그니처를 구현"""
    return session.exec(
        select(FewShot)
        .where(FewShot.is_active == True)
        .where(FewShot.intent_type == intent_type)
        .order_by(FewShot.created_at.desc())
    ).all()
```

**핵심 플로우:**
```
User Query → QueryRouter (intent 분류) → Service (_get_active_fewshots) → LLM (프롬프트 + few-shots) → Response → query_logs 저장
```

관리 UI에서 `query_logs` → Few-shot 승격 → 다음 질의부터 자동 반영

#### 3. Singleton Service Pattern
모든 서비스는 모듈 레벨에서 인스턴스화 (FastAPI 라이프사이클과 독립):
```python
# backend/app/services/ollama_service.py
class OllamaService:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        # ...

ollama_service = OllamaService()  # 싱글톤

# backend/app/api/analysis.py
from app.services.ollama_service import ollama_service  # import로 재사용
```

#### 4. DB Session Management (Dependency Injection)
FastAPI `Depends(get_session)`으로 DB 세션 자동 관리:
```python
# backend/app/api/chat.py
@router.post("/")
async def chat(request: ChatRequest, session: Session = Depends(get_session)):
    # session은 자동으로 생성/종료
    intent = await query_router.classify_intent_simple(request.query, session)
```

#### 5. PostgreSQL Trigger Audit Pattern ([init.sql](init.sql))
Few-shot 변경 이력을 애플리케이션 코드가 아닌 DB 트리거로 자동 기록:
```sql
CREATE FUNCTION log_few_shot_audit() RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO few_shot_audit (few_shot_id, action, old_value)
        VALUES (OLD.id, 'DELETE', row_to_json(OLD));
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO few_shot_audit (few_shot_id, action, old_value, new_value)
        VALUES (NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW));
    -- INSERT 케이스 생략
END;
$$ LANGUAGE plpgsql;
```

**Why Trigger Instead of Application Code:**
- 코드 버그로 인한 audit 누락 방지 (100% 보장)
- DB 레벨 원자성 (트랜잭션과 함께 커밋)
- 직접 SQL 실행 시에도 audit 기록됨

#### 6. Air-Gapped Model Cache Pattern ([qdrant_service.py](backend/app/services/qdrant_service.py))
FastEmbed 모델을 사전 다운로드하여 오프라인 로드:
```python
# Force offline mode BEFORE importing TextEmbedding
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

class QdrantService:
    def __init__(self):
        fastembed_cache = os.getenv("FASTEMBED_CACHE_PATH", "/app/fastembed_cache")
        self.embedding_model = TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            cache_dir=fastembed_cache  # 사전 다운로드된 모델
        )
```

**폐쇄망 배포 워크플로:**
1. 인터넷 환경: `backend/fastembed_cache/`에 모델 다운로드
2. Docker 이미지 빌드: `Dockerfile.offline`에서 cache 디렉토리 COPY
3. 폐쇄망 서버: 볼륨 마운트 없이 이미지에서 직접 로드
4. 런타임: `HF_HUB_OFFLINE=1`로 인터넷 접근 차단 보장

#### 7. Multi-Stage RAG Pattern ([query_decomposer.py](backend/app/services/query_decomposer.py), [rag_service.py](backend/app/services/rag_service.py))
사용자 질의를 비정형/정형으로 분해하고 연관성 분석을 제공하는 3단계 파이프라인:

**Stage 1: Query Decomposition**
```python
# backend/app/services/query_decomposer.py
async def decompose_query(self, original_query: str) -> Dict[str, Any]:
    """
    질의를 분해하여 반환:
    - unstructured_query: 문맥 기반 검색용 (비정형)
    - structured_query: 필드값 추출용 (정형)
    - needs_db_query: DB 쿼리 필요 여부
    - decomposition_reasoning: 분류 사유
    """
```

**Stage 2: RAG Search with Decomposed Query**
```python
# backend/app/services/rag_service.py
async def answer_question_with_analysis(
    self,
    original_query: str,
    search_query: str,  # 분해된 비정형 질의
    top_k: int = 3,
    session: Optional[Session] = None
):
    # 1. 비정형 질의로 Qdrant 검색
    # 2. Few-shot 예제 주입
    # 3. LLM 답변 생성
    # 4. 연관성 분석 (Stage 3)
```

**Stage 3: Relevance Analysis**
```python
async def _analyze_relevance(
    self,
    original_query: str,
    search_query: str,
    search_results: List[Dict],
    answer: str
) -> Dict[str, Any]:
    """
    검색 결과의 연관성 분석:
    - reasoning: 왜 이 답변이 나왔는지 설명
    - confidence: 신뢰도 점수 (0.0~1.0)
    - matched_sections: 사용된 문서 섹션
    """
```

**Why Multi-Stage:**
- **정형 데이터의 유연한 정의**: RDB 컬럼뿐만 아니라 문서 내 구조화된 필드(금액, 날짜 등)도 정형으로 분류
- **검색 품질 향상**: 원본 질의 대신 재구성된 비정형 질의로 검색하여 semantic match 개선
- **설명 가능성**: 분해 사유 + 연관성 분석으로 AI 답변의 투명성 확보
- **하이브리드 지원**: `needs_db_query=true` → SQL Agent로 자동 라우팅

#### 8. Phase 2: LangChain LCEL Chain Pattern ([rag_chain.py](backend/app/chains/rag_chain.py))
Phase 1의 200줄 커스텀 RAG 구현을 LangChain LCEL로 50줄로 축약:

**핵심 구조:**
```python
# LCEL Runnable 파이프라인
self.chain = (
    {
        "context": RunnableLambda(self._format_docs),
        "question": RunnablePassthrough(),
        "few_shot_examples": RunnableLambda(lambda x: "")
    }
    | self.prompt  # ChatPromptTemplate
    | self.llm     # OllamaLLM
    | StrOutputParser()
)

# 사용
answer = await self.chain.ainvoke({
    "docs": docs,
    "question": question,
    "few_shot_examples": few_shot_examples
})
```

**Benefits:**
- **Async-first**: `ainvoke()` 기본 지원 (Phase 1은 수동으로 async 처리)
- **LangSmith 자동 추적**: 모든 chain invocation이 자동으로 추적됨
- **Composable**: `|` 연산자로 체인 확장 용이
- **표준화**: LangChain 생태계와 호환

**Trade-offs:**
- Phase 1 대비 1.2GB 의존성 증가 (FastAPI 앱: 767MB → 1.9GB)
- 폐쇄망 배포 시 추가 패키지 다운로드 필요

#### 9. Phase 2: LangGraph Workflow Pattern ([chat_graph.py](backend/app/graphs/chat_graph.py))
Two-Tier Intent Classification을 LangGraph StateMachine으로 시각화:

**State 정의:**
```python
class ChatState(TypedDict):
    query: str
    session: Any
    intent: str  # "rag_search", "sql_query", "general", "unknown"
    intent_candidates: List[str]
    answer: str
    sources: List[dict]
    sql: Optional[str]
    results: Optional[List[dict]]
```

**Graph 구성:**
```python
workflow = StateGraph(ChatState)

# 노드 추가
workflow.add_node("check_intent", check_intent_table)  # Tier 1
workflow.add_node("classify_llm", classify_with_llm)   # Tier 2
workflow.add_node("rag", execute_rag)
workflow.add_node("sql", execute_sql)
workflow.add_node("general", execute_general)

# 조건부 라우팅
workflow.add_conditional_edges(
    "check_intent",
    route_by_intent,  # intent에 따라 분기
    {
        "classify_llm": "classify_llm",
        "rag": "rag",
        "sql": "sql",
        "general": "general"
    }
)
```

**Why LangGraph:**
- **시각화**: Mermaid 다이어그램으로 워크플로 자동 생성 (디버깅 용이)
- **상태 관리**: ChatState 중앙 집중식 관리 (Phase 1은 변수 전달)
- **확장성**: 새 노드/엣지 추가가 직관적 (if/else 분기보다 유지보수 쉬움)
- **LangSmith 통합**: 각 노드의 입/출력이 자동으로 추적됨

**사용 예:**
```python
# API에서 사용 (chat.py)
chat_graph = get_chat_graph()
result = await chat_graph.ainvoke({
    "query": "계약서에서 금액은?",
    "session": session,
    "intent": "unknown",
    "intent_candidates": [],
    "answer": "",
    "sources": [],
    "sql": None,
    "results": None
})
# result["answer"], result["intent"], result["sources"] 사용
```

### 데이터베이스 스키마 (PostgreSQL)
- `applicant_info`: 지원자 정보 (읽기 전용, CRUD 없음)
- `intents`: 키워드 → intent_type 매핑 (Two-tier 분류 Tier 1)
- `query_logs`: 모든 질의 자동 저장 (Few-shot 후보)
- `few_shots`: 승격된 Few-shot 예제 (LLM 프롬프트에 주입)
- `few_shot_audit`: 변경 이력 (PostgreSQL 트리거로 자동 기록)

상세 스키마: [init.sql](init.sql)

### 디렉토리 구조
```
backend/app/
├── api/              # API 엔드포인트
│   ├── analysis.py   # 지원자 분석 API
│   ├── chat.py       # RAG 채팅 API (Phase 2: ChatGraph 사용)
│   ├── upload.py     # 문서 업로드 API
│   ├── intent.py     # Intent 관리 API
│   ├── query_log.py  # Query Log 관리 API
│   └── fewshot.py    # Few-shot 관리 API
├── chains/           # Phase 2: LangChain LCEL Chains
│   └── rag_chain.py  # RAG Chain (200줄 → 50줄)
├── graphs/           # Phase 2: LangGraph 워크플로
│   └── chat_graph.py # ChatGraph (Two-Tier Intent Classification)
├── models/           # 데이터 모델 (SQLModel)
├── services/         # 비즈니스 로직 (싱글톤, Phase 1 fallback)
│   ├── ollama_service.py   # LLM 호출
│   ├── qdrant_service.py   # 벡터 DB 검색
│   ├── rag_service.py      # RAG 파이프라인 (Phase 1 fallback)
│   ├── query_router.py     # Intent 분류 (Two-tier)
│   └── sql_agent.py        # NL→SQL 변환
├── database.py       # DB 연결 및 세션 관리
└── main.py           # FastAPI 앱 및 라우터 등록
```

## Environment Variables

**필수 (.env):**
- `DATABASE_URL`: PostgreSQL 연결 (예: `postgresql://admin:admin123@postgres:5432/applicants_db`)
- `OLLAMA_BASE_URL`: Ollama API (예: `http://ollama:11434`)
- `OLLAMA_MODEL`: `llama3.2:1b`
- `QDRANT_URL`: Qdrant API (예: `http://qdrant:6333`)
- `FASTEMBED_CACHE_PATH`: FastEmbed 모델 캐시 디렉토리 (예: `/app/fastembed_cache`)

**Phase 2 필수 (LangSmith):**
- `LANGCHAIN_API_KEY`: LangSmith API 키 (https://smith.langchain.com에서 발급)
- `LANGCHAIN_TRACING_V2`: `true` (LangSmith 추적 활성화)
- `LANGCHAIN_PROJECT`: `llmproject-phase2` (프로젝트 이름)

**선택:**
- `QDRANT_COLLECTION_NAME`: `documents` (default)
- `EMBEDDING_MODEL`: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (default)
- `DB_SCHEMA`: `public` (default)

## Development Workflow

### 코드 변경
```bash
# Hot reload (docker-compose.dev.yml 사용 시 자동 반영)
# backend/app/ 디렉토리는 볼륨 마운트되어 있음

# 환경 변수 변경: 재시작만
docker-compose restart backend

# 의존성 변경 (requirements.txt): 재빌드
docker-compose up -d --build backend
```

### DB 마이그레이션
1. SQL 파일 작성 (수동, Alembic 없음)
2. `psql`로 로컬 테스트
3. `init.sql` 업데이트 (새 설치 환경용)
4. 폐쇄망 서버: PostgreSQL 컨테이너에서 수동 실행

### API 테스트
- API 문서: http://localhost:8000/docs
- Intent 분류 디버깅: `POST /api/chat/classify {"query": "..."}`
- 질의 분해 디버깅: `POST /api/chat/decompose {"query": "..."}`
- LangSmith 추적 확인: https://smith.langchain.com → Projects → llmproject-phase2

### Phase 2 개발 가이드

#### LangChain Chain 추가
1. **`backend/app/chains/` 디렉토리에 새 Chain 생성**
   ```python
   # backend/app/chains/new_chain.py
   from langchain_core.prompts import ChatPromptTemplate
   from langchain_core.output_parsers import StrOutputParser
   from langchain_ollama import OllamaLLM

   class NewChain:
       def __init__(self):
           self.llm = OllamaLLM(...)
           self.prompt = ChatPromptTemplate.from_messages([...])
           self.chain = self.prompt | self.llm | StrOutputParser()

       async def invoke(self, input_data):
           return await self.chain.ainvoke(input_data)
   ```

2. **싱글톤 인스턴스 생성**
   ```python
   _new_chain_instance = None

   def get_new_chain():
       global _new_chain_instance
       if _new_chain_instance is None:
           _new_chain_instance = NewChain()
       return _new_chain_instance
   ```

3. **API 또는 Graph에서 사용**
   ```python
   from app.chains.new_chain import get_new_chain

   new_chain = get_new_chain()
   result = await new_chain.invoke({"input": "..."})
   ```

#### LangGraph 워크플로 수정
1. **`chat_graph.py`에서 새 노드 추가**
   ```python
   async def execute_new_task(state: ChatState) -> ChatState:
       # 노드 로직
       return state

   workflow.add_node("new_task", execute_new_task)
   ```

2. **라우팅 엣지 업데이트**
   ```python
   workflow.add_conditional_edges(
       "check_intent",
       route_by_intent,
       {
           "new_task": "new_task",  # 새 엣지 추가
           # 기존 엣지 유지...
       }
   )
   ```

3. **ChatState에 필드 추가** (필요한 경우)
   ```python
   class ChatState(TypedDict):
       # 기존 필드...
       new_field: Optional[str]
   ```

#### LangSmith 디버깅
1. **추적 확인**: https://smith.langchain.com → llmproject-phase2
2. **특정 Chain만 추적 비활성화**:
   ```python
   from langsmith import traceable

   @traceable(run_type="chain", name="my_custom_chain")
   async def my_function(...):
       # 커스텀 이름으로 추적
   ```

3. **환경 변수로 추적 off**:
   ```bash
   LANGCHAIN_TRACING_V2=false docker-compose restart backend
   ```

### 성능 특성 이해
**예상 응답 시간 (llama3.2:1b 기준):**
- Two-tier Tier 1 (키워드 매칭): < 100ms
- Two-tier Tier 2 (LLM 분류): 2-5초
- 기본 RAG (`/api/chat/`): 3-8초 (LLM 1회 호출)
- **Enhanced RAG (`/api/chat/enhanced`)**: 8-15초 (LLM 3회 호출)
  - Query Decomposition: 2-3초
  - RAG 답변 생성: 3-5초
  - Relevance Analysis: 3-5초
- SQL 쿼리 (NL→SQL + 실행 + 해석): 3-6초

**최적화 포인트:**
- `intents` 테이블에 자주 사용되는 키워드 추가 → LLM 호출 60-80% 감소
- Few-shot 예제 승격 → LLM 응답 품질 향상 (속도는 거의 동일)
- Qdrant 문서 수 증가 → 검색 시간은 로그 스케일 증가 (1000개까지 < 50ms)
- Multi-Stage RAG 병렬 처리: 연관성 분석을 백그라운드 실행 (구현 가능)

## Adding Features

### 새 Intent Type 추가
1. **`QueryRouter`의 `QueryIntent` enum 확장** ([query_router.py](backend/app/services/query_router.py:12))
   ```python
   class QueryIntent(str, Enum):
       RAG_SEARCH = "rag_search"
       SQL_QUERY = "sql_query"
       GENERAL = "general"
       NEW_INTENT = "new_intent"  # 추가
   ```

2. **서비스 핸들러 생성** (예: `backend/app/services/new_service.py`)
   - 필수: `_get_active_fewshots(session, intent_type="new_intent")` 메서드 구현
   - Few-shots를 프롬프트에 주입하여 LLM 호출

3. **Chat API 라우팅 추가** ([chat.py](backend/app/api/chat.py))
   ```python
   elif intent == QueryIntent.NEW_INTENT:
       result = await new_service.handle(query, session)
   ```

4. **`intents` 테이블에 키워드 추가** (관리 UI 또는 SQL)
   ```sql
   INSERT INTO intents (keyword, intent_type, priority, description)
   VALUES ('새키워드', 'new_intent', 10, '새로운 의도');
   ```

5. **Few-shot 예제 추가** (관리 UI: Query Logs → 승격)

6. **테스트**: `POST /api/chat/classify {"query": "새키워드 포함 질문"}`

### 새 분석 API 추가
1. `OllamaService`에 메서드 추가 ([ollama_service.py](backend/app/services/ollama_service.py))
2. API 엔드포인트 추가 ([analysis.py](backend/app/api/analysis.py))
3. `main.py`에 라우터 자동 포함됨 (analysis_router 이미 등록)

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

### 네트워크 문제
```bash
docker network inspect dev-network
docker network connect dev-network backend
```

## Important Constraints

- **Read-Only Applicant DB**: `applicant_info` 테이블은 읽기 전용 (CRUD 없음, 분석만)
- **No Auto-Migration**: 테이블 생성 안 함 (폐쇄망 서버는 `init.sql` 사전 실행 필수)
- **Manual Few-shot Curation**: Query logs → 관리 UI 검토 → 승격 버튼 (자동 승격 없음)
- **Audit Trail**: PostgreSQL 트리거로 Few-shot 변경 이력 자동 기록
- **Korean-Only**: 모든 프롬프트 한국어 (다국어 지원 없음)
- **Phase 2 Migration**: LangChain/LangGraph 추가 (1.2GB 의존성), Phase 1 서비스는 fallback으로 유지
- **Hybrid Architecture**: Phase 2 Chains/Graphs 우선 사용, Phase 1 Services는 호환성 유지 또는 미구현 기능용
- **Offline Deployment**: `Dockerfile.offline` + 사전 다운로드된 패키지 사용 ([DEPLOY.md](DEPLOY.md))
- **Security**: SQL Agent는 패턴 매칭만 사용 (동적 SQL 실행 금지, SQL injection 방지)
- **LangSmith Requirement**: Phase 2 기능 사용 시 LangSmith API 키 필수 (무료 Developer 플랜 가능)

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
```

### 디버깅 체크리스트
1. **Intent 분류 안됨**: `POST /api/chat/classify` → `intents` 테이블 키워드 추가
2. **LLM 응답 없음**: `docker logs ollama` → 모델 다운로드 확인
3. **RAG 답변 부정확**: Few-shot 예제 추가, Qdrant 문서 확인
4. **DB 연결 실패**: `.env` `DATABASE_URL` 확인, 네트워크 연결 확인
5. **임베딩 모델 로드 실패**: `FASTEMBED_CACHE_PATH` 볼륨 마운트 확인

### Phase 2 전용 디버깅
1. **LangSmith 추적 안됨**:
   - `.env`에서 `LANGCHAIN_TRACING_V2=true` 확인
   - `LANGCHAIN_API_KEY` 유효성 확인 (https://smith.langchain.com/settings)
   - Backend 로그에서 "LangSmith tracing enabled" 메시지 확인

2. **ChatGraph 실행 오류**:
   - `docker logs backend`에서 LangGraph 에러 확인
   - ChatState의 모든 필드가 초기화되었는지 확인
   - 노드 함수가 async로 정의되었는지 확인

3. **RAG Chain 실행 오류**:
   - Qdrant collection이 존재하는지 확인: `curl http://localhost:6333/collections`
   - FastEmbed 모델이 로드되었는지 확인: backend 로그에서 "Loading model" 메시지
   - LCEL Chain 구성 확인: `self.chain` 파이프라인 오류

4. **Phase 1 fallback 확인**:
   - `/api/chat/enhanced` (Phase 1 Multi-Stage RAG) vs `/api/chat/` (Phase 2 ChatGraph)
   - `api/chat.py`에서 어느 구현을 사용하는지 확인
   - Phase 1 services는 여전히 유효함 (rag_service, sql_agent, ollama_service)

## Key Request Flows

### Phase 2: ChatGraph 요청 플로우 (LangGraph)
```
[POST /api/chat/] {"query": "계약서에서 금액은?"}
    ↓
[chat.py:18] ChatGraph.ainvoke({query, session, intent="unknown", ...})
    ↓
[chat_graph.py] check_intent_table(state)
    ├─→ [query_router.py:107] _check_intent_table(query, session)
    │   ├─→ "계약서" LIKE 검색 → intents 테이블 매칭 (1개)
    │   └─→ state["intent"] = "rag_search" (Tier 1 완료, LLM 호출 없음)
    ↓
[chat_graph.py] route_by_intent(state) → returns "rag"
    ↓
[chat_graph.py] execute_rag(state)
    └─→ RAGChain.invoke(query, session, top_k=3)
        ├─→ [rag_chain.py:153] vectorstore.similarity_search(query) → Qdrant 검색
        ├─→ [rag_chain.py:163] _get_active_fewshots(session, "rag_search")
        ├─→ [rag_chain.py:166] LCEL Chain 실행
        │   └─→ format_docs | prompt | ollama | parser
        │   └─→ LangSmith 자동 추적 활성화!
        └─→ [rag_chain.py:173] return {"answer": ..., "sources": [...]}
    ↓
[chat_graph.py] state["answer"] = result["answer"]
[chat_graph.py] state["sources"] = result["sources"]
    ↓
[chat.py:76] QueryLog 생성 및 DB 저장
    └─→ query_text, detected_intent, response, created_at 기록
    ↓
[chat.py:82] return ChatResponse(answer=..., intent=...)
```

**핵심 경로 파일 (Phase 2):**
- [chat.py](backend/app/api/chat.py) - 메인 라우터
- [chat_graph.py](backend/app/graphs/chat_graph.py) - LangGraph 워크플로
- [rag_chain.py](backend/app/chains/rag_chain.py) - LangChain LCEL RAG Chain
- [query_router.py](backend/app/services/query_router.py) - Two-tier 분류 (재사용)
- [qdrant_service.py](backend/app/services/qdrant_service.py) - 벡터 검색 (재사용)

**LangSmith 추적 확인:**
- https://smith.langchain.com → Projects → llmproject-phase2
- 각 요청의 ChatGraph 노드별 입/출력, LCEL Chain 단계별 처리 시간 확인 가능

### Phase 1: 전체 Chat 요청 플로우 (커스텀 구현, fallback)
```
[POST /api/chat/] {"query": "계약서에서 금액은?"}
    ↓
[chat.py:18] QueryRouter.classify_intent_simple(query, session)
    ├─→ [query_router.py:107] _check_intent_table(query, session)
    │   ├─→ "계약서" LIKE 검색 → intents 테이블 매칭 (1개)
    │   └─→ return QueryIntent.RAG_SEARCH (Tier 1 완료, LLM 호출 없음)
    ↓
[chat.py:26] if intent == QueryIntent.RAG_SEARCH:
    └─→ RAGService.answer_question(query, session)
        ├─→ [rag_service.py:55] _get_active_fewshots(session, "rag_search")
        │   └─→ few_shots 테이블에서 is_active=true 예제 로드
        ├─→ [rag_service.py:62] QdrantService.search_documents(query)
        │   ├─→ TextEmbedding.embed(query) → 768차원 벡터
        │   └─→ Qdrant.search(vector, top_k=3) → 관련 문서 반환
        ├─→ [rag_service.py:70] _build_prompt(few_shots, context, query)
        │   └─→ 프롬프트 구조: [Few-shot 예제들] + [검색된 문서] + [질문]
        ├─→ [rag_service.py:78] OllamaService.generate(prompt)
        │   └─→ Ollama API 호출 → LLM 답변 생성
        └─→ [rag_service.py:84] return {"answer": ..., "sources": [...]}
    ↓
[chat.py:76] QueryLog 생성 및 DB 저장
    └─→ query_text, detected_intent, response, created_at 기록
    ↓
[chat.py:82] return ChatResponse(answer=..., intent=...)
```

**핵심 경로 파일:**
- [chat.py](backend/app/api/chat.py) - 메인 라우터
- [query_router.py](backend/app/services/query_router.py) - Two-tier 분류
- [rag_service.py](backend/app/services/rag_service.py) - RAG 파이프라인
- [qdrant_service.py](backend/app/services/qdrant_service.py) - 벡터 검색
- [ollama_service.py](backend/app/services/ollama_service.py) - LLM 호출

### Few-Shot 승격 플로우
```
[관리 UI: Query Logs 탭]
    ↓
[사용자가 query_log ID 1번 선택 → "Promote to Few-Shot" 버튼 클릭]
    ↓
[POST /api/query-logs/convert-to-fewshot]
    └─→ [query_log.py:66] convert_to_fewshot(body, session)
        ├─→ [query_log.py:73] QueryLog.get(id=1) → 원본 로그 조회
        ├─→ [query_log.py:78] FewShot 객체 생성
        │   └─→ source_query_log_id=1, user_query=..., expected_response=...
        ├─→ [query_log.py:84] session.add(few_shot), session.commit()
        │   └─→ PostgreSQL Trigger 자동 실행:
        │       └─→ few_shot_audit_trigger → INSERT into few_shot_audit
        ├─→ [query_log.py:88] query_log.is_converted_to_fewshot = True
        └─→ [query_log.py:92] return created FewShot
    ↓
[다음 RAG 요청부터 자동으로 해당 예제가 프롬프트에 포함됨]
```

### Multi-Stage RAG 요청 플로우
```
[POST /api/chat/enhanced] {"query": "계약 배경과 금액 알려줘"}
    ↓
[chat.py:113] QueryDecomposer.decompose_query(query)
    ├─→ [query_decomposer.py:16] LLM 호출: 질의 분석
    └─→ {
          "unstructured_query": "계약 체결 배경과 목적",
          "structured_query": "계약 금액",
          "needs_db_query": false,
          "decomposition_reasoning": "배경은 문맥 이해 필요(비정형), 금액은 필드값(정형)"
        }
    ↓
[chat.py:116] QueryRouter.classify_intent_simple(query, session)
    └─→ Intent: rag_search (intents 테이블 매칭)
    ↓
[chat.py:124] RAGService.answer_question_with_analysis()
    ├─→ [rag_service.py:90] Qdrant.search("계약 체결 배경과 목적")
    │   └─→ 관련 문서 3개 검색 (비정형 질의 사용)
    ├─→ [rag_service.py:108] _get_active_fewshots(session, "rag_search")
    ├─→ [rag_service.py:111] _build_prompt(few_shots, context, query)
    ├─→ [rag_service.py:112] Ollama.generate(prompt) → 답변 생성
    └─→ [rag_service.py:115] _analyze_relevance()
        ├─→ [rag_service.py:188] LLM 호출: 연관성 분석
        └─→ {
              "reasoning": "검색된 계약서 1페이지에 배경 명시, 3페이지에 금액 직접 기재",
              "confidence": 0.92,
              "matched_sections": ["1페이지 배경", "3페이지 계약조건"]
            }
    ↓
[chat.py:132] ChatResponse 생성
    ├─→ answer: "..."
    ├─→ decomposition: {...}
    └─→ relevance_analysis: {...}
    ↓
[chat.py:167] QueryLog 저장
    ↓
[chat.py:175] return ChatResponse
```

**핵심 경로 파일 (Multi-Stage RAG):**
- [chat.py](backend/app/api/chat.py) - `/enhanced` 엔드포인트
- [query_decomposer.py](backend/app/services/query_decomposer.py) - 질의 분해
- [rag_service.py](backend/app/services/rag_service.py) - RAG + 연관성 분석
- [chat.py](backend/app/models/chat.py) - QueryDecomposition, RelevanceAnalysis 모델
