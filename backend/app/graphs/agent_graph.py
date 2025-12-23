"""
Agent Graph - Tool-based LangGraph 워크플로
LLM이 Tool을 선택하고 실행하는 ReAct Agent 패턴
"""
import os
from typing import TypedDict, Annotated, Sequence, Optional
from operator import add

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from sqlmodel import Session, select

from app.tools.document_tools import AVAILABLE_TOOLS
from app.models.query_log import QueryLog


class AgentState(TypedDict):
    """
    Agent 상태 정의

    LangGraph의 표준 패턴:
    - messages: 대화 이력 (HumanMessage, AIMessage, ToolMessage)
    - session_context: DB 세션 등의 런타임 컨텍스트
    """
    messages: Annotated[Sequence[BaseMessage], add]  # 메시지 추가 방식
    session_context: dict  # Tool에 전달할 컨텍스트


def build_system_prompt_with_fewshots(session: Optional[Session]) -> str:
    """
    Few-shot 예제를 포함한 시스템 프롬프트 생성 (Agent 레벨)

    DDD 관점:
    - Agent가 "어떻게 학습하는가"는 Agent 도메인
    - Tool은 "무엇을 하는가"만 책임
    - Few-shot은 Agent의 프롬프트 엔지니어링 영역

    Args:
        session: DB 세션 (Few-shot 조회용)

    Returns:
        시스템 프롬프트 문자열
    """
    base_prompt = """당신은 문서 검색 및 데이터 분석을 돕는 AI 어시스턴트입니다.

사용자의 질문을 분석하여 적절한 도구(Tool)를 선택하고 실행하세요.

## 사용 가능한 도구
1. **search_documents**: 업로드된 문서(계약서, 제안서 등)에서 정보 검색
2. **query_database**: 지원자 데이터베이스 조회 (통계, 필터링 등)
3. **general_conversation**: 일반 대화 및 간단한 질문 답변

## 도구 선택 가이드
- "문서에서", "계약서", "제안서" → search_documents
- "지원자", "명 있어?", "통계", "SQL" → query_database
- "안녕", "어떻게", "설명해줘" (도구 불필요) → general_conversation
"""

    if not session:
        return base_prompt

    # QueryLog에서 Few-shot 예제 조회 (최근 성공 케이스)
    try:
        few_shot_logs = session.exec(
            select(QueryLog)
            .where(QueryLog.response.isnot(None))  # 응답이 있는 것만
            .order_by(QueryLog.created_at.desc())
            .limit(5)
        ).all()

        if few_shot_logs:
            examples = []
            for log in few_shot_logs:
                examples.append(
                    f"질문: {log.query_text}\n"
                    f"답변: {log.response[:100]}..."
                )

            few_shot_section = "\n## 참고 예제\n" + "\n\n".join(examples)
            return base_prompt + few_shot_section

    except Exception as e:
        print(f"Few-shot 조회 실패: {e}")

    return base_prompt


async def agent_node(state: AgentState) -> AgentState:
    """
    Agent 노드: LLM이 Tool을 선택

    LLM이 사용자 질의를 보고:
    1. Tool을 호출할지 결정
    2. 어떤 Tool을 호출할지 선택
    3. Tool 호출 인자를 생성

    Few-shot 프롬프트는 Agent 레벨에서 주입 (DDD 원칙)
    """
    messages = state["messages"]
    session = state["session_context"].get("session")

    # Ollama LLM with Tool Calling
    llm = ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
        temperature=0.7
    )

    # Tool binding (Ollama가 Tool 스키마를 받아서 선택)
    llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)

    # Few-shot 시스템 프롬프트 생성 (Agent 책임)
    system_prompt = build_system_prompt_with_fewshots(session)

    # 첫 메시지가 시스템 메시지가 아니면 추가
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_prompt)] + list(messages)

    # LLM 호출 (Tool 선택 또는 일반 답변)
    response = await llm_with_tools.ainvoke(messages)

    # 응답을 메시지 리스트에 추가
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """
    조건부 라우팅: LLM이 Tool을 호출했는지 확인

    Returns:
        "tools": Tool 호출 필요 → ToolNode로 이동
        "end": 최종 답변 → 종료
    """
    messages = state["messages"]
    last_message = messages[-1]

    # AIMessage에 tool_calls가 있으면 Tool 실행 필요
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # 아니면 종료
    return "end"


def create_agent_graph() -> StateGraph:
    """
    Agent Graph 생성 (LangGraph 표준 패턴)

    플로우:
    1. START → agent (LLM이 Tool 선택)
    2. agent → should_continue (조건 분기)
    3-A. should_continue → tools (Tool 실행)
    3-B. should_continue → END (최종 답변)
    4. tools → agent (Tool 결과를 보고 다시 추론)
    """
    # StateGraph 초기화
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(AVAILABLE_TOOLS))

    # 시작점: agent
    workflow.set_entry_point("agent")

    # 조건부 엣지: agent → tools or END
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Tool 실행 후 다시 agent로
    workflow.add_edge("tools", "agent")

    return workflow.compile()


# 싱글톤 인스턴스
_agent_graph_instance = None


def get_agent_graph():
    """Agent Graph 싱글톤 반환"""
    global _agent_graph_instance

    if _agent_graph_instance is None:
        _agent_graph_instance = create_agent_graph()

    return _agent_graph_instance
