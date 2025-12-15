"""
채팅 및 문서 업로드 관련 Pydantic 모델
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    query: str


class QueryDecomposition(BaseModel):
    """질의 분해 결과"""
    unstructured_query: Optional[str] = None
    structured_query: Optional[str] = None
    needs_db_query: bool = False
    decomposition_reasoning: str = ""


class RelevanceAnalysis(BaseModel):
    """연관성 분석 결과"""
    reasoning: str
    confidence: float
    matched_sections: List[str] = []


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    answer: str
    intent: str  # rag_search, sql_query, general
    sources: Optional[List[Dict[str, Any]]] = None
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    # Multi-stage RAG 추가 필드
    decomposition: Optional[QueryDecomposition] = None
    relevance_analysis: Optional[RelevanceAnalysis] = None


class UploadResponse(BaseModel):
    """파일 업로드 응답 모델"""
    message: str
    filename: str
    doc_id: str
    text_length: int
