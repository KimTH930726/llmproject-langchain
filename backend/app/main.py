from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, chat, upload


app = FastAPI(
    title="지원자 자기소개서 분석 및 RAG 채팅 API",
    description="PostgreSQL 지원자 분석, RAG 기반 문서 검색 및 채팅 서비스",
    version="2.0.0"
)

# CORS 설정 (폐쇄망 환경 대응)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 개발 서버
        "http://localhost",       # Nginx (포트 80)
        "http://localhost:80",    # Nginx 명시적 포트
        "*"                       # 폐쇄망 환경에서 IP 접근 허용
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(analysis.router)     # 지원자 분석 API
app.include_router(chat.router)         # Tool-based Agent 채팅 API
app.include_router(upload.router)       # 문서 업로드 API

@app.get("/")
async def root():
    return {
        "message": "Tool-based Agent RAG 시스템",
        "version": "2.0.0",
        "architecture": "LangChain + LangGraph + Tool Calling",
        "features": [
            "지원자 분석 (요약, 키워드, 면접질문)",
            "Tool-based Agent (LLM이 Tool 자동 선택)",
            "문서 검색 (search_documents tool)",
            "데이터베이스 조회 (query_database tool)",
            "일반 대화 (general_conversation tool)",
            "LangSmith 자동 추적"
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
