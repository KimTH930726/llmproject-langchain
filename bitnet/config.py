"""
BitNet 설정 관리

환경 변수 및 경로 설정을 중앙 관리합니다.
"""

import os
from pathlib import Path

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
BITNET_CPP_DIR = PROJECT_ROOT / "bitnet-cpp"

# 바이너리 경로
BUILD_DIR = BITNET_CPP_DIR / "build"
LLAMA_CLI = BUILD_DIR / "bin" / "llama-cli"
LLAMA_SERVER = BUILD_DIR / "bin" / "llama-server"
LLAMA_BENCH = BUILD_DIR / "bin" / "llama-bench"
LLAMA_QUANTIZE = BUILD_DIR / "bin" / "llama-quantize"

# 모델 경로
MODELS_DIR = BITNET_CPP_DIR / "models"
DEFAULT_MODEL_DIR = MODELS_DIR / "BitNet-b1.58-2B-4T"
DEFAULT_GGUF_MODEL = DEFAULT_MODEL_DIR / "ggml-model-i2_s.gguf"

# HuggingFace 모델 저장소
HF_GGUF_REPO = "microsoft/BitNet-b1.58-2B-4T-gguf"
HF_BF16_REPO = "microsoft/bitnet-b1.58-2B-4T-bf16"
HF_MAIN_REPO = "microsoft/BitNet-b1.58-2B-4T"

# 추론 기본 설정
DEFAULT_THREADS = min(os.cpu_count() or 4, 8)
DEFAULT_CTX_SIZE = 2048
DEFAULT_TEMPERATURE = 0.7
DEFAULT_N_PREDICT = 256
DEFAULT_BATCH_SIZE = 1

# 서버 설정
BITNET_SERVER_HOST = os.getenv("BITNET_SERVER_HOST", "127.0.0.1")
BITNET_SERVER_PORT = int(os.getenv("BITNET_SERVER_PORT", "8080"))


def get_model_path() -> Path:
    """환경 변수 또는 기본 경로에서 모델 경로 반환"""
    env_path = os.getenv("BITNET_MODEL_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_GGUF_MODEL


def is_model_available() -> bool:
    """모델 파일이 존재하는지 확인"""
    model_path = get_model_path()
    return model_path.exists() and model_path.stat().st_size > 0


def is_binary_available() -> bool:
    """bitnet.cpp 바이너리가 빌드되었는지 확인"""
    return LLAMA_CLI.exists()
