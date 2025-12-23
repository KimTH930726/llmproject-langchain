"""
Chat API V2 - Tool-based Agent 아키텍처

기존 Phase 2 (ChatGraph)를 Tool-based Agent로 재구현
- Intent 테이블 제거
- LLM이 Tool을 직접 선택
- ReAct Agent 패턴
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from langchain_core.messages import HumanMessage, AIMessage

from app.models.chat import ChatRequest, ChatResponse
from app.models.query_log import QueryLog
from app.graphs.agent_graph import get_agent_graph
from app.database import get_session

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    Tool-based Agent를 사용한 채팅 API

    흐름:
    1. 사용자 질의 → Agent Graph
    2. Agent가 Tool 선택 (search_documents, query_database, general_conversation)
    3. Tool 실행 → 결과 반환
    4. Query Log 자동 저장

    장점:
    - Intent 테이블 불필요 (LLM이 직접 추론)
    - 확장성: 새 Tool 추가만으로 기능 확장
    - 표준 패턴: LangGraph + ToolNode
    """
    query = request.query

    try:
        # Agent Graph 가져오기
        agent_graph = get_agent_graph()

        # 초기 상태 구성
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "session_context": {"session": session}
        }

        # Agent 실행 (LangSmith 자동 추적)
        result = await agent_graph.ainvoke(initial_state)

        # 최종 메시지 추출
        messages = result["messages"]
        last_message = messages[-1]

        # AIMessage의 content 추출
        if isinstance(last_message, AIMessage):
            answer = last_message.content
        else:
            answer = str(last_message)

        # Query Log 저장
        query_log = QueryLog(
            query_text=query,
            response=answer,
            detected_intent=None  # Intent 분류 제거
        )
        session.add(query_log)
        session.commit()

        return ChatResponse(
            answer=answer,
            intent=None,  # Intent 개념 제거
            sources=[],   # Tool에서 반환된 정보는 answer에 포함됨
            query_log_id=query_log.id
        )

    except Exception as e:
        # 에러 로깅
        print(f"Agent 실행 오류: {e}")
        import traceback
        traceback.print_exc()

        # Query Log에 에러 기록
        error_log = QueryLog(
            query_text=query,
            response=f"오류 발생: {str(e)}",
            detected_intent=None
        )
        session.add(error_log)
        session.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Agent 실행 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(
    limit: int = 10,
    session: Session = Depends(get_session)
):
    """
    최근 대화 이력 조회

    Args:
        limit: 조회할 개수 (기본 10개)
    """
    from sqlmodel import select, desc

    logs = session.exec(
        select(QueryLog)
        .order_by(desc(QueryLog.created_at))
        .limit(limit)
    ).all()

    return {
        "history": [
            {
                "id": log.id,
                "query": log.query_text,
                "response": log.response,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }
