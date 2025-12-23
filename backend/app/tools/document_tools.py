"""
Document Tools - LangChain Tool 정의
RAG 검색, SQL 쿼리, 일반 대화를 Tool로 구현
"""
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from sqlmodel import Session, select

from app.chains.rag_chain import get_rag_chain
from app.services.sql_agent import SQLAgent
from app.services.ollama_service import ollama_service
from app.models.applicant import Applicant


@tool
async def search_documents(query: str, session_context: Dict[str, Any]) -> str:
    """
    업로드된 문서에서 관련 정보를 검색합니다.

    계약서, 제안서, 기술 문서 등에서 특정 내용을 찾을 때 사용하세요.

    Args:
        query: 검색할 질문 (예: "계약서에서 금액은?", "프로젝트 일정은?")
        session_context: DB 세션을 포함한 컨텍스트

    Returns:
        검색 결과 및 관련 문서 정보
    """
    rag_chain = get_rag_chain()
    session = session_context.get("session")

    result = await rag_chain.invoke(
        question=query,
        session=session,
        top_k=3
    )

    # Tool은 문자열을 반환해야 함 (LangChain 규약)
    answer = result["answer"]
    sources = result.get("sources", [])

    if sources:
        sources_text = "\n\n참조 문서:\n" + "\n".join([
            f"- {src['text'][:100]}..." for src in sources[:2]
        ])
        return f"{answer}\n{sources_text}"

    return answer


@tool
async def query_database(query: str, session_context: Dict[str, Any]) -> str:
    """
    지원자 데이터베이스에서 정보를 조회합니다.

    지원자 수, 특정 기술 스택 보유자, 경력별 통계 등을 조회할 때 사용하세요.

    Args:
        query: 조회 질문 (예: "Python 개발자 수는?", "5년 이상 경력자는?")
        session_context: DB 세션을 포함한 컨텍스트

    Returns:
        쿼리 결과를 자연어로 해석한 답변
    """
    session = session_context.get("session")
    sql_agent = SQLAgent()

    result = await sql_agent.execute_query(query, session)

    # 에러 처리
    if "error" in result:
        return f"데이터베이스 조회 실패: {result['answer']}"

    # 결과 포맷팅
    answer = result["answer"]
    sql = result.get("sql", "")
    count = result.get("count", 0)

    return f"{answer}\n\n(실행 SQL: {sql}, {count}건 조회)"


@tool
async def general_conversation(query: str, session_context: Dict[str, Any]) -> str:
    """
    일반적인 대화나 간단한 질문에 답변합니다.

    인사, 시스템 사용법, 기타 문서나 DB와 관련 없는 질문에 사용하세요.

    Args:
        query: 사용자 질문
        session_context: 컨텍스트 (세션 등)

    Returns:
        자연어 답변
    """
    # Ollama 직접 호출 (Few-shot 없이 간단한 대화)
    response = await ollama_service.generate(
        prompt=query,
        system_prompt="당신은 친절한 문서 검색 및 데이터 분석 AI 어시스턴트입니다. 사용자를 도와주세요."
    )

    return response.get("response", "죄송합니다. 답변을 생성할 수 없습니다.")


# Tool 목록 (Agent에서 사용)
AVAILABLE_TOOLS = [
    search_documents,
    query_database,
    general_conversation
]
