"""
BitNet b1.58 서비스 - FastAPI 백엔드 통합

bitnet.cpp 바이너리를 활용하여 CPU 전용 1-bit LLM 추론을 제공합니다.
기존 OllamaService와 동일한 패턴(싱글톤 + Lazy Init)을 따릅니다.

아키텍처 포인트:
- Subprocess 기반 추론 (llama-cli)
- llama-server 기반 HTTP API (선택적)
- Ollama 대체 또는 병렬 운용 가능
"""

import asyncio
import subprocess
import time
import logging
import os
import signal
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 프로젝트 루트에서 bitnet-cpp 경로 계산
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_BITNET_CPP_DIR = _PROJECT_ROOT / "bitnet-cpp"
_LLAMA_CLI = _BITNET_CPP_DIR / "build" / "bin" / "llama-cli"
_LLAMA_SERVER = _BITNET_CPP_DIR / "build" / "bin" / "llama-server"
_DEFAULT_MODEL = _BITNET_CPP_DIR / "models" / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"


class BitNetService:
    """
    BitNet b1.58 추론 서비스

    OllamaService와 유사한 인터페이스를 제공하여
    기존 Agent/Tool 시스템에서 LLM 백엔드를 교체할 수 있습니다.
    """

    def __init__(self):
        self.model_path = os.getenv("BITNET_MODEL_PATH", str(_DEFAULT_MODEL))
        self.threads = int(os.getenv("BITNET_THREADS", str(min(os.cpu_count() or 4, 8))))
        self.ctx_size = int(os.getenv("BITNET_CTX_SIZE", "2048"))
        self.temperature = float(os.getenv("BITNET_TEMPERATURE", "0.7"))
        self.n_predict = int(os.getenv("BITNET_N_PREDICT", "256"))

        # llama-server 프로세스 (선택적 HTTP API)
        self._server_proc: Optional[subprocess.Popen] = None
        self._server_host = os.getenv("BITNET_SERVER_HOST", "127.0.0.1")
        self._server_port = int(os.getenv("BITNET_SERVER_PORT", "8080"))

    @property
    def is_available(self) -> bool:
        """바이너리와 모델이 모두 존재하는지 확인"""
        return (
            _LLAMA_CLI.exists()
            and Path(self.model_path).exists()
            and Path(self.model_path).stat().st_size > 0
        )

    async def generate(self, prompt: str, n_predict: Optional[int] = None) -> str:
        """
        텍스트 생성 (비동기)

        Args:
            prompt: 입력 프롬프트
            n_predict: 생성할 토큰 수

        Returns:
            생성된 텍스트
        """
        if not self.is_available:
            raise RuntimeError(
                "BitNet이 사용 불가합니다. "
                "바이너리 빌드와 모델 다운로드를 확인하세요: bash bitnet/setup.sh --status"
            )

        n_predict = n_predict or self.n_predict

        command = [
            str(_LLAMA_CLI),
            "-m", self.model_path,
            "-n", str(n_predict),
            "-t", str(self.threads),
            "-p", prompt,
            "-ngl", "0",
            "-c", str(self.ctx_size),
            "--temp", str(self.temperature),
            "-b", "1",
            "--no-display-prompt",
        ]

        logger.info(f"BitNet 추론 시작: prompt_len={len(prompt)}, n_predict={n_predict}")
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            elapsed = time.time() - start_time
            output = stdout.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.error(f"BitNet 추론 실패: {error_msg}")
                return f"[BitNet 오류] {error_msg[:200]}"

            logger.info(f"BitNet 추론 완료: {elapsed:.2f}초")
            return output

        except asyncio.TimeoutError:
            logger.error("BitNet 추론 타임아웃 (300초)")
            return "[BitNet 오류] 추론 타임아웃"

    async def generate_with_metrics(
        self, prompt: str, n_predict: Optional[int] = None
    ) -> dict:
        """
        성능 메트릭을 포함한 텍스트 생성

        Returns:
            {"response": str, "elapsed_seconds": float, "tokens_per_second": float, ...}
        """
        if not self.is_available:
            return {
                "response": "",
                "error": "BitNet 사용 불가",
                "elapsed_seconds": 0,
                "tokens_per_second": 0,
            }

        n_predict = n_predict or self.n_predict

        command = [
            str(_LLAMA_CLI),
            "-m", self.model_path,
            "-n", str(n_predict),
            "-t", str(self.threads),
            "-p", prompt,
            "-ngl", "0",
            "-c", str(self.ctx_size),
            "--temp", str(self.temperature),
            "-b", "1",
            "--no-display-prompt",
        ]

        start_time = time.time()
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        elapsed = time.time() - start_time

        output = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace")

        # stderr에서 성능 메트릭 파싱
        tps = 0.0
        tokens_generated = n_predict
        for line in stderr_text.split("\n"):
            if "eval time" in line and "tokens per second" in line:
                try:
                    tps_part = line.split("tokens per second")[0].rsplit(",", 1)[-1].strip()
                    tps = float(tps_part)
                except (ValueError, IndexError):
                    pass
                try:
                    token_part = line.split("/")[1].strip().split()[0]
                    tokens_generated = int(token_part)
                except (ValueError, IndexError):
                    pass

        if tps == 0.0 and elapsed > 0:
            tps = tokens_generated / elapsed

        return {
            "response": output,
            "elapsed_seconds": round(elapsed, 3),
            "tokens_per_second": round(tps, 2),
            "tokens_generated": tokens_generated,
            "threads": self.threads,
            "model": os.path.basename(self.model_path),
        }

    def get_status(self) -> dict:
        """서비스 상태 반환"""
        return {
            "available": self.is_available,
            "binary_exists": _LLAMA_CLI.exists(),
            "model_exists": Path(self.model_path).exists(),
            "model_path": self.model_path,
            "threads": self.threads,
            "ctx_size": self.ctx_size,
            "architecture": "BitNet b1.58 (1.58-bit, CPU-only)",
            "model_info": {
                "name": "BitNet-b1.58-2B-4T",
                "params": "2.4B",
                "quantization": "1.58-bit (ternary: {-1, 0, +1})",
                "context_length": 4096,
                "gguf_size": "~1.19 GB",
            },
        }


# 싱글톤 인스턴스
bitnet_service = BitNetService()
