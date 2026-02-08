"""
BitNet b1.58 추론 러너

bitnet.cpp의 llama-cli 바이너리를 래핑하여
Python에서 쉽게 추론을 실행할 수 있게 합니다.
"""

import subprocess
import json
import time
import logging
from typing import Optional
from dataclasses import dataclass, field

from bitnet.config import (
    LLAMA_CLI,
    LLAMA_SERVER,
    get_model_path,
    is_model_available,
    is_binary_available,
    DEFAULT_THREADS,
    DEFAULT_CTX_SIZE,
    DEFAULT_TEMPERATURE,
    DEFAULT_N_PREDICT,
    DEFAULT_BATCH_SIZE,
    BITNET_SERVER_HOST,
    BITNET_SERVER_PORT,
)

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """추론 결과를 담는 데이터 클래스"""
    text: str
    tokens_generated: int = 0
    elapsed_seconds: float = 0.0
    tokens_per_second: float = 0.0
    model_path: str = ""
    threads: int = 0
    error: Optional[str] = None


class BitNetRunner:
    """
    BitNet b1.58 추론 러너

    bitnet.cpp의 llama-cli를 subprocess로 호출하여 추론을 실행합니다.
    Lazy Initialization 패턴을 따르며, 실제 추론 시에만 바이너리를 검증합니다.

    Usage:
        runner = BitNetRunner()
        result = runner.generate("한국의 수도는 어디인가요?")
        print(result.text)
        print(f"Speed: {result.tokens_per_second:.2f} tok/s")
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        threads: int = DEFAULT_THREADS,
        ctx_size: int = DEFAULT_CTX_SIZE,
        temperature: float = DEFAULT_TEMPERATURE,
        n_predict: int = DEFAULT_N_PREDICT,
    ):
        self.model_path = model_path or str(get_model_path())
        self.threads = threads
        self.ctx_size = ctx_size
        self.temperature = temperature
        self.n_predict = n_predict
        self._validated = False

    def _validate(self):
        """바이너리와 모델 존재 확인"""
        if self._validated:
            return

        if not is_binary_available():
            raise FileNotFoundError(
                f"bitnet.cpp 바이너리를 찾을 수 없습니다: {LLAMA_CLI}\n"
                "먼저 빌드를 실행하세요: bash bitnet/setup.sh --build-only"
            )
        if not is_model_available():
            raise FileNotFoundError(
                f"BitNet 모델을 찾을 수 없습니다: {self.model_path}\n"
                "모델을 다운로드하세요: bash bitnet/setup.sh --download-only"
            )
        self._validated = True

    def generate(
        self,
        prompt: str,
        n_predict: Optional[int] = None,
        temperature: Optional[float] = None,
        conversation: bool = False,
    ) -> InferenceResult:
        """
        프롬프트로 텍스트 생성

        Args:
            prompt: 입력 프롬프트
            n_predict: 생성할 토큰 수 (기본값: self.n_predict)
            temperature: 온도 파라미터 (기본값: self.temperature)
            conversation: 대화 모드 활성화 여부

        Returns:
            InferenceResult: 생성된 텍스트와 성능 메트릭
        """
        self._validate()

        n_predict = n_predict or self.n_predict
        temperature = temperature if temperature is not None else self.temperature

        command = [
            str(LLAMA_CLI),
            "-m", self.model_path,
            "-n", str(n_predict),
            "-t", str(self.threads),
            "-p", prompt,
            "-ngl", "0",
            "-c", str(self.ctx_size),
            "--temp", str(temperature),
            "-b", str(DEFAULT_BATCH_SIZE),
            "--no-display-prompt",
        ]

        if conversation:
            command.append("-cnv")

        logger.info(f"BitNet 추론 시작: threads={self.threads}, n_predict={n_predict}")
        start_time = time.time()

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )
            elapsed = time.time() - start_time

            if proc.returncode != 0:
                logger.error(f"BitNet 추론 실패: {proc.stderr}")
                return InferenceResult(
                    text="",
                    error=proc.stderr,
                    elapsed_seconds=elapsed,
                    model_path=self.model_path,
                    threads=self.threads,
                )

            output_text = proc.stdout.strip()

            # stderr에서 성능 메트릭 파싱 시도
            tokens_generated = n_predict
            tps = 0.0
            for line in proc.stderr.split("\n"):
                if "eval time" in line and "token" in line:
                    try:
                        # "eval time = 1234.56 ms / 128 tokens (9.65 ms per token, 103.63 tokens per second)"
                        parts = line.split("tokens per second)")
                        if parts:
                            tps_str = parts[0].rsplit(",", 1)[-1].strip()
                            tps = float(tps_str)
                    except (ValueError, IndexError):
                        pass
                if "eval time" in line:
                    try:
                        token_part = line.split("/")[1].strip().split()[0]
                        tokens_generated = int(token_part)
                    except (ValueError, IndexError):
                        pass

            if tps == 0.0 and elapsed > 0:
                tps = tokens_generated / elapsed

            result = InferenceResult(
                text=output_text,
                tokens_generated=tokens_generated,
                elapsed_seconds=elapsed,
                tokens_per_second=tps,
                model_path=self.model_path,
                threads=self.threads,
            )

            logger.info(
                f"BitNet 추론 완료: {tokens_generated} tokens, "
                f"{elapsed:.2f}s, {tps:.2f} tok/s"
            )
            return result

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return InferenceResult(
                text="",
                error="추론 타임아웃 (300초 초과)",
                elapsed_seconds=elapsed,
                model_path=self.model_path,
                threads=self.threads,
            )

    def start_server(
        self,
        host: str = BITNET_SERVER_HOST,
        port: int = BITNET_SERVER_PORT,
    ) -> subprocess.Popen:
        """
        llama-server를 백그라운드로 시작하여 OpenAI 호환 API 제공

        Returns:
            subprocess.Popen: 서버 프로세스 핸들
        """
        self._validate()

        if not LLAMA_SERVER.exists():
            raise FileNotFoundError(f"llama-server 바이너리를 찾을 수 없습니다: {LLAMA_SERVER}")

        command = [
            str(LLAMA_SERVER),
            "-m", self.model_path,
            "-t", str(self.threads),
            "-c", str(self.ctx_size),
            "--host", host,
            "--port", str(port),
            "-ngl", "0",
            "-b", str(DEFAULT_BATCH_SIZE),
        ]

        logger.info(f"BitNet 서버 시작: {host}:{port}")
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc

    def get_status(self) -> dict:
        """현재 BitNet 환경 상태 확인"""
        return {
            "binary_available": is_binary_available(),
            "model_available": is_model_available(),
            "model_path": self.model_path,
            "threads": self.threads,
            "ctx_size": self.ctx_size,
            "llama_cli": str(LLAMA_CLI),
        }


# 싱글톤 인스턴스 (Lazy)
_runner_instance = None


def get_bitnet_runner() -> BitNetRunner:
    """BitNetRunner 싱글톤 인스턴스 반환"""
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = BitNetRunner()
    return _runner_instance
