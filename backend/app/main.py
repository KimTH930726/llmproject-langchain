from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, chat, upload, intent, fewshot, query_log


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
app.include_router(analysis.router)     # 기존 분석 API
app.include_router(chat.router)         # 신규 채팅 API
app.include_router(upload.router)       # 신규 업로드 API
app.include_router(intent.router)       # Intent 관리 API
app.include_router(query_log.router)    # 질의 로그 관리 API (신규)
app.include_router(fewshot.router)      # Few-shot 관리 API

@app.get("/")
async def root():
    return {
        "message": "지원자 자기소개서 분석 및 RAG 채팅 API",
        "features": [
            "지원자 분석 (요약, 키워드, 면접질문)",
            "문서 업로드 및 벡터 저장",
            "RAG 기반 문서 검색",
            "자연어 SQL 쿼리",
            "Intent 관리 (쿼리 의도 분류)",
            "Few-shot 관리 (예제 학습 데이터)"
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
