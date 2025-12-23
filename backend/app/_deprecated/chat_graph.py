"""
ChatGraph - LangGraph 기반 채팅 워크플로

Two-Tier Intent Classification을 LangGraph로 시각화
- Tier 1: intents 테이블 키워드 매칭 (빠름)
- Tier 2: LLM 기반 분류 (fallback)
"""
from typing import TypedDict, Literal, Any, Optional, List
from langgraph.graph import StateGraph, END
from sqlmodel import Session

from app.services.query_router import query_router, QueryIntent
from app.chains.rag_chain import get_rag_chain
from app.services.sql_agent import sql_agent
from app.services.ollama_service import ollama_service


class ChatState(TypedDict):
    """
    채팅 워크플로 상태

    LangGraph의 각 노드는 이 상태를 읽고 수정합니다.
    """
    # 입력
    query: str
    session: Any  # DB Session (SQLModel Session)

    # Intent 분류 상태
    intent: str  # "rag_search", "sql_query", "general", "unknown"
    intent_candidates: List[str]  # Tier 1에서 여러 개 매칭된 경우

    # 출력
    answer: str
    sources: List[dict]  # RAG 검색 결과
    sql: Optional[str]  # SQL 쿼리 (sql_query인 경우)
    results: Optional[List[dict]]  # SQL 실행 결과


# ==========================================
# 노드 함수들 (워크플로의 각 단계)
# ==========================================

def check_intent_table(state: ChatState) -> ChatState:
    """
    Tier 1: intents 테이블에서 키워드 매칭

    Returns:
        - intent: 1개만 매칭되면 해당 intent
        - intent_candidates: 2개 이상 매칭되면 후보 리스트
        - intent="unknown": 매칭 없음
    """
    session = state["session"]
    query = state["query"]

    # QueryRouter의 _check_intent_table 메서드 재사용
    result = query_router._check_intent_table(query, session)

    if isinstance(result, QueryIntent):
        # 1개만 매칭 - 즉시 사용
        state["intent"] = result.value
    elif isinstance(result, list):
        # 2개 이상 매칭 - LLM으로 disambiguate 필요
        state["intent_candidates"] = result
        state["intent"] = "unknown"
    else:
        # 매칭 없음 - LLM으로 분류
        state["intent"] = "unknown"
        state["intent_candidates"] = []

    return state


async def classify_with_llm(state: ChatState) -> ChatState:
    """
    Tier 2: LLM 기반 Intent 분류

    Tier 1에서 매칭 실패했거나 애매한 경우 호출됨
    """
    query = state["query"]
    intent_candidates = state.get("intent_candidates", [])

    # QueryRouter의 classify_intent 메서드 사용
    intent = await query_router.classify_intent(
        query,
        intent_candidates=intent_candidates if intent_candidates else None
    )

    state["intent"] = intent.value
    return state


async def execute_rag(state: ChatState) -> ChatState:
    """
    RAG Chain 실행 (문서 검색 + LLM 답변)
    """
    query = state["query"]
    session = state["session"]

    # Phase 2 RAG Chain 사용
    rag_chain = get_rag_chain()
    result = await rag_chain.invoke(query, session=session, top_k=3)

    state["answer"] = result["answer"]
    state["sources"] = result.get("sources", [])

    return state


async def execute_sql(state: ChatState) -> ChatState:
    """
    SQL Agent 실행 (자연어 → SQL → 결과 해석)
    """
    query = state["query"]
    session = state["session"]

    # Phase 1 SQL Agent 재사용 (나중에 LangChain SQL Agent로 교체 예정)
    result = await sql_agent.execute_query(query, session=session)

    state["answer"] = result["answer"]
    state["sql"] = result.get("sql")
    state["results"] = result.get("results")

    return state


async def execute_general(state: ChatState) -> ChatState:
    """
    일반 대화 (Few-shot + LLM)
    """
    query = state["query"]
    session = state["session"]

    # Phase 1 OllamaService 재사용
    answer = await ollama_service.generate_with_fewshot(
        query,
        session=session,
        intent_type="general"
    )

    state["answer"] = answer

    return state


# ==========================================
# 라우팅 함수 (조건부 분기)
# ==========================================

def route_by_intent(state: ChatState) -> str:
    """
    Intent에 따라 다음 노드 결정

    Returns:
        - "classify_llm": LLM으로 분류 필요
        - "rag": RAG 검색
        - "sql": SQL 쿼리
        - "general": 일반 대화
    """
    intent = state["intent"]

    if intent == "unknown":
        return "classify_llm"
    elif intent == QueryIntent.RAG_SEARCH.value:
        return "rag"
    elif intent == QueryIntent.SQL_QUERY.value:
        return "sql"
    else:  # QueryIntent.GENERAL.value
        return "general"


# ==========================================
# LangGraph 워크플로 구성
# ==========================================

def create_chat_graph() -> StateGraph:
    """
    ChatGraph 생성

    워크플로:
    1. check_intent_table (Tier 1)
       ├─ 1개 매칭 → rag/sql/general
       ├─ 2+ 매칭 → classify_llm (Tier 2)
       └─ 0개 매칭 → classify_llm (Tier 2)
    2. classify_llm (필요한 경우만)
       └─ rag/sql/general
    3. rag/sql/general
       └─ END
    """
    workflow = StateGraph(ChatState)

    # 노드 추가
    workflow.add_node("check_intent", check_intent_table)
    workflow.add_node("classify_llm", classify_with_llm)
    workflow.add_node("rag", execute_rag)
    workflow.add_node("sql", execute_sql)
    workflow.add_node("general", execute_general)

    # 시작점
    workflow.set_entry_point("check_intent")

    # 조건부 엣지 (check_intent → 다음 노드)
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

    # 조건부 엣지 (classify_llm → 다음 노드)
    workflow.add_conditional_edges(
        "classify_llm",
        route_by_intent,
        {
            "rag": "rag",
            "sql": "sql",
            "general": "general"
        }
    )

    # 종료 엣지
    workflow.add_edge("rag", END)
    workflow.add_edge("sql", END)
    workflow.add_edge("general", END)

    return workflow.compile()


# 싱글톤 그래프 인스턴스
_chat_graph_instance = None


def get_chat_graph():
    """ChatGraph 싱글톤 인스턴스 반환"""
    global _chat_graph_instance

    if _chat_graph_instance is None:
        _chat_graph_instance = create_chat_graph()

    return _chat_graph_instance
