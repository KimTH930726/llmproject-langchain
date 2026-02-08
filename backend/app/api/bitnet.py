"""
BitNet b1.58 API 엔드포인트

CPU 기반 1-bit LLM 추론 API를 제공합니다.
기존 Chat API와 독립적으로 운영되며, BitNet의 성능을 직접 테스트할 수 있습니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.bitnet_service import bitnet_service

router = APIRouter(prefix="/api/bitnet", tags=["BitNet b1.58"])


class GenerateRequest(BaseModel):
    """텍스트 생성 요청"""
    prompt: str = Field(..., description="입력 프롬프트", min_length=1)
    n_predict: Optional[int] = Field(None, description="생성할 토큰 수", ge=1, le=4096)
    temperature: Optional[float] = Field(None, description="온도 파라미터", ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    """텍스트 생성 응답"""
    response: str
    elapsed_seconds: float
    tokens_per_second: float
    tokens_generated: int
    threads: int
    model: str


class StatusResponse(BaseModel):
    """BitNet 상태 응답"""
    available: bool
    binary_exists: bool
    model_exists: bool
    model_path: str
    threads: int
    ctx_size: int
    architecture: str
    model_info: dict


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    BitNet 환경 상태 확인

    바이너리 빌드 여부, 모델 다운로드 여부, 설정 정보를 반환합니다.
    """
    return bitnet_service.get_status()


@router.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """
    BitNet b1.58로 텍스트 생성

    CPU 전용 1.58-bit 양자화 모델을 사용하여 텍스트를 생성합니다.
    성능 메트릭(토큰 생성 속도, 소요 시간)을 함께 반환합니다.
    """
    if not bitnet_service.is_available:
        status = bitnet_service.get_status()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "BitNet이 사용 불가합니다",
                "binary_exists": status["binary_exists"],
                "model_exists": status["model_exists"],
                "setup_guide": "bash bitnet/setup.sh --status 로 상태를 확인하세요",
            },
        )

    result = await bitnet_service.generate_with_metrics(
        prompt=request.prompt,
        n_predict=request.n_predict,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/chat")
async def chat(request: GenerateRequest):
    """
    간단한 챗 인터페이스

    시스템 프롬프트와 함께 대화형 응답을 생성합니다.
    """
    if not bitnet_service.is_available:
        raise HTTPException(status_code=503, detail="BitNet 사용 불가")

    chat_prompt = f"""You are a helpful AI assistant. Respond in Korean.

User: {request.prompt}
Assistant:"""

    result = await bitnet_service.generate_with_metrics(
        prompt=chat_prompt,
        n_predict=request.n_predict or 256,
    )

    return {
        "query": request.prompt,
        "response": result.get("response", ""),
        "metrics": {
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "tokens_per_second": result.get("tokens_per_second", 0),
            "tokens_generated": result.get("tokens_generated", 0),
        },
    }
