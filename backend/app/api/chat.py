"""
채팅 API
QueryRouter로 의도를 분류하고 RAG 또는 SQL Agent로 응답 생성
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session

from app.models.chat import ChatRequest, ChatResponse, QueryDecomposition, RelevanceAnalysis
from app.models.query_log import QueryLog
from app.services.query_router import query_router, QueryIntent
from app.services.rag_service import rag_service
from app.services.sql_agent import sql_agent
from app.services.ollama_service import ollama_service
from app.services.query_decomposer import query_decomposer
from app.database import get_session

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    사용자 질의에 대해 적절한 방식으로 응답 생성

    흐름:
    1. QueryRouter로 의도 분류 (RAG / SQL / General)
    2. RAG: Qdrant에서 문서 검색 후 LLM으로 답변
    3. SQL: 자연어를 SQL로 변환하여 DB 조회 후 답변
    4. General: LLM으로 직접 응답
    5. 질의와 응답을 query_logs 테이블에 자동 저장

    - query: 사용자 질의
    """
    query = request.query
    answer = None
    intent_value = None

    try:
        # 1. 의도 분류 (intents 테이블 우선, 없으면 LLM으로 분류)
        intent = await query_router.classify_intent_simple(query, session=session)
        intent_value = intent.value

        # 2. 의도별 처리 (모든 서비스에 session 전달하여 Few-shot 예제 활용)
        if intent == QueryIntent.RAG_SEARCH:
            # RAG 검색
            result = await rag_service.answer_question(query, top_k=3, session=session)
            answer = result["answer"]
            response = ChatResponse(
                answer=answer,
                intent=intent_value,
                sources=result.get("sources", [])
            )

        elif intent == QueryIntent.SQL_QUERY:
            # SQL Agent 실행 (Few-shot 포함)
            result = await sql_agent.execute_query(query, session=session)
            answer = result["answer"]
            response = ChatResponse(
                answer=answer,
                intent=intent_value,
                sql=result.get("sql"),
                results=result.get("results")
            )

        else:  # QueryIntent.GENERAL
            # 일반 대화 (Few-shot 포함)
            answer = await ollama_service.generate_with_fewshot(query, session=session, intent_type="general")
            response = ChatResponse(
                answer=answer,
                intent=intent_value
            )

        # 3. 질의 로그 자동 저장
        query_log = QueryLog(
            query_text=query,
            detected_intent=intent_value,
            response=answer
        )
        session.add(query_log)
        session.commit()

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 실패: {str(e)}")


@router.post("/enhanced", response_model=ChatResponse)
async def chat_enhanced(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    Multi-Stage RAG: 질의 분해 + 연관성 분석 포함

    흐름:
    1. QueryDecomposer로 질의 분해 (비정형/정형 분류 + 사유)
    2. Intent 분류 (RAG / SQL / General)
    3. RAG: 비정형 질의로 검색 + 연관성 분석
    4. SQL: 정형 질의로 DB 조회 (needs_db_query=true인 경우)
    5. 결과에 분해 사유 + 연관성 분석 포함

    - query: 사용자 질의
    """
    query = request.query
    answer = None
    intent_value = None

    try:
        # Stage 1: 질의 분해
        decomposition_result = await query_decomposer.decompose_query(query)

        # Stage 2: Intent 분류
        intent = await query_router.classify_intent_simple(query, session=session)
        intent_value = intent.value

        # Stage 3: Intent별 처리
        if intent == QueryIntent.RAG_SEARCH:
            # 비정형 질의로 RAG 검색 + 연관성 분석
            search_query = decomposition_result.get("unstructured_query") or query

            result = await rag_service.answer_question_with_analysis(
                original_query=query,
                search_query=search_query,
                top_k=3,
                session=session
            )

            answer = result["answer"]
            response = ChatResponse(
                answer=answer,
                intent=intent_value,
                sources=result.get("sources", []),
                decomposition=QueryDecomposition(**decomposition_result),
                relevance_analysis=RelevanceAnalysis(**result.get("relevance_analysis", {
                    "reasoning": "",
                    "confidence": 0.0,
                    "matched_sections": []
                }))
            )

        elif intent == QueryIntent.SQL_QUERY or decomposition_result.get("needs_db_query"):
            # 정형 질의로 SQL 실행
            structured_query = decomposition_result.get("structured_query") or query

            result = await sql_agent.execute_query(structured_query, session=session)
            answer = result["answer"]
            response = ChatResponse(
                answer=answer,
                intent=intent_value,
                sql=result.get("sql"),
                results=result.get("results"),
                decomposition=QueryDecomposition(**decomposition_result)
            )

        else:  # QueryIntent.GENERAL
            answer = await ollama_service.generate_with_fewshot(query, session=session, intent_type="general")
            response = ChatResponse(
                answer=answer,
                intent=intent_value,
                decomposition=QueryDecomposition(**decomposition_result)
            )

        # 질의 로그 자동 저장
        query_log = QueryLog(
            query_text=query,
            detected_intent=intent_value,
            response=answer
        )
        session.add(query_log)
        session.commit()

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced 채팅 처리 실패: {str(e)}")


@router.post("/classify")
async def classify_query(request: ChatRequest, session: Session = Depends(get_session)):
    """
    질의 의도 분류만 수행 (디버깅용)

    - query: 사용자 질의
    """
    try:
        intent_simple = await query_router.classify_intent_simple(request.query, session=session)
        intent_llm = await query_router.classify_intent(request.query)

        return {
            "query": request.query,
            "intent_simple": intent_simple.value,
            "intent_llm": intent_llm.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분류 실패: {str(e)}")


@router.post("/decompose")
async def decompose_query_debug(request: ChatRequest):
    """
    질의 분해만 수행 (디버깅용)

    - query: 사용자 질의
    """
    try:
        result = await query_decomposer.decompose_query(request.query)
        return {
            "query": request.query,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"질의 분해 실패: {str(e)}")
