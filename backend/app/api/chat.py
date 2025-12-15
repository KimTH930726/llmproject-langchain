"""
채팅 API - Phase 2: ChatGraph 통합

Phase 1: QueryRouter + if/else 분기
Phase 2: LangGraph ChatGraph (시각화된 워크플로)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session

from app.models.chat import ChatRequest, ChatResponse, QueryDecomposition, RelevanceAnalysis
from app.models.query_log import QueryLog
from app.graphs.chat_graph import get_chat_graph  # Phase 2: ChatGraph
from app.services.query_decomposer import query_decomposer
from app.database import get_session

# Phase 1 imports (fallback용)
from app.services.query_router import query_router, QueryIntent
from app.services.rag_service import rag_service
from app.services.sql_agent import sql_agent
from app.services.ollama_service import ollama_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_session)
):
    """
    사용자 질의에 대해 적절한 방식으로 응답 생성

    Phase 2: LangGraph ChatGraph 워크플로 사용
    - Two-Tier Intent Classification (시각화)
    - LangSmith 자동 추적
    - 상태 기반 실행

    흐름:
    1. ChatGraph 실행 (check_intent → classify_llm → rag/sql/general)
    2. 질의 로그 자동 저장
    3. LangSmith에 추적 기록

    - query: 사용자 질의
    """
    query = request.query

    try:
        # Phase 2: ChatGraph 실행 (LangGraph 워크플로)
        chat_graph = get_chat_graph()

        result = await chat_graph.ainvoke({
            "query": query,
            "session": session,
            "intent": "unknown",
            "intent_candidates": [],
            "answer": "",
            "sources": [],
            "sql": None,
            "results": None
        })

        # ChatGraph 결과에서 응답 생성
        response = ChatResponse(
            answer=result["answer"],
            intent=result["intent"],
            sources=result.get("sources", []),
            sql=result.get("sql"),
            results=result.get("results")
        )

        # 질의 로그 자동 저장
        query_log = QueryLog(
            query_text=query,
            detected_intent=result["intent"],
            response=result["answer"]
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
