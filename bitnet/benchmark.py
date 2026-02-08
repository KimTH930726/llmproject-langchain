#!/usr/bin/env python3
"""
BitNet b1.58 벤치마크 스크립트

CPU 점유율, 메모리 사용량, 토큰 생성 속도를 종합적으로 측정합니다.
llama-bench 바이너리와 직접 추론 두 가지 방식으로 측정합니다.

Usage:
    # 기본 벤치마크
    python -m bitnet.benchmark

    # 상세 옵션
    python -m bitnet.benchmark --threads 4 8 16 --n-tokens 64 128 256

    # llama-bench 사용 (prompt processing + generation 모두 측정)
    python -m bitnet.benchmark --use-llama-bench
"""

import argparse
import json
import os
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, asdict
from typing import List, Optional

from bitnet.config import (
    LLAMA_CLI,
    LLAMA_BENCH,
    get_model_path,
    is_model_available,
    is_binary_available,
    DEFAULT_THREADS,
)


@dataclass
class BenchmarkResult:
    """벤치마크 결과"""
    test_name: str
    threads: int
    n_tokens: int
    n_prompt: int
    elapsed_seconds: float
    tokens_per_second: float
    avg_cpu_percent: float
    peak_memory_mb: float
    model: str


def _monitor_resources(pid: int, stop_event: threading.Event, results: dict):
    """별도 스레드에서 CPU/메모리 사용률 모니터링"""
    cpu_samples = []
    mem_samples = []

    try:
        import resource
    except ImportError:
        pass

    while not stop_event.is_set():
        try:
            # /proc 기반 CPU/메모리 모니터링 (Linux)
            stat_path = f"/proc/{pid}/stat"
            status_path = f"/proc/{pid}/status"

            if os.path.exists(status_path):
                with open(status_path, "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            mem_kb = int(line.split()[1])
                            mem_samples.append(mem_kb / 1024)  # MB
                            break

            # CPU 점유율은 /proc/stat에서 측정
            if os.path.exists(stat_path):
                with open(stat_path, "r") as f:
                    fields = f.read().split()
                    utime = int(fields[13])
                    stime = int(fields[14])
                    cpu_samples.append(utime + stime)

        except (FileNotFoundError, ProcessLookupError, IndexError):
            pass

        stop_event.wait(0.1)

    # CPU 사용률 계산 (jiffies 기반)
    if len(cpu_samples) >= 2:
        total_jiffies = cpu_samples[-1] - cpu_samples[0]
        elapsed_jiffies = len(cpu_samples) * 10  # ~100ms 간격, 1 jiffy = 10ms
        if elapsed_jiffies > 0:
            results["avg_cpu_percent"] = (total_jiffies / elapsed_jiffies) * 100
    else:
        results["avg_cpu_percent"] = 0.0

    results["peak_memory_mb"] = max(mem_samples) if mem_samples else 0.0


def run_inference_benchmark(
    threads: int,
    n_tokens: int,
    n_prompt: int = 32,
    model_path: Optional[str] = None,
) -> BenchmarkResult:
    """
    직접 추론 방식 벤치마크

    llama-cli로 실제 텍스트를 생성하면서 성능을 측정합니다.
    """
    model = model_path or str(get_model_path())

    # 한국어 테스트 프롬프트
    prompt = "인공지능의 미래에 대해 설명해 주세요. 특히 1-bit 양자화 기술이 가져올 변화에 대해 자세히 논의해 주세요."

    command = [
        str(LLAMA_CLI),
        "-m", model,
        "-n", str(n_tokens),
        "-t", str(threads),
        "-p", prompt,
        "-ngl", "0",
        "-c", "2048",
        "--temp", "0.7",
        "-b", "1",
        "--no-display-prompt",
    ]

    print(f"\n{'='*60}")
    print(f"  BitNet 추론 벤치마크")
    print(f"  Threads: {threads} | Tokens: {n_tokens} | Prompt: ~{n_prompt} tokens")
    print(f"{'='*60}")

    # 리소스 모니터링 시작
    resource_results = {"avg_cpu_percent": 0.0, "peak_memory_mb": 0.0}

    start_time = time.time()
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=_monitor_resources,
        args=(proc.pid, stop_event, resource_results),
        daemon=True,
    )
    monitor_thread.start()

    stdout, stderr = proc.communicate(timeout=600)
    elapsed = time.time() - start_time

    stop_event.set()
    monitor_thread.join(timeout=2)

    # stderr에서 토큰 속도 파싱
    tps = 0.0
    actual_tokens = n_tokens
    stderr_text = stderr.decode("utf-8", errors="replace")

    for line in stderr_text.split("\n"):
        if "eval time" in line and "tokens per second" in line:
            try:
                # "eval time =   XXX ms /  YYY tokens ( ZZZ ms per token,  WW.WW tokens per second)"
                tps_part = line.split("tokens per second")[0].rsplit(",", 1)[-1].strip()
                tps = float(tps_part)
            except (ValueError, IndexError):
                pass
            try:
                token_part = line.split("/")[1].strip().split()[0]
                actual_tokens = int(token_part)
            except (ValueError, IndexError):
                pass

    if tps == 0.0 and elapsed > 0:
        tps = actual_tokens / elapsed

    result = BenchmarkResult(
        test_name="inference",
        threads=threads,
        n_tokens=actual_tokens,
        n_prompt=n_prompt,
        elapsed_seconds=round(elapsed, 3),
        tokens_per_second=round(tps, 2),
        avg_cpu_percent=round(resource_results["avg_cpu_percent"], 1),
        peak_memory_mb=round(resource_results["peak_memory_mb"], 1),
        model=os.path.basename(model),
    )

    _print_result(result)
    return result


def run_llama_bench(
    threads: int,
    n_tokens: int = 128,
    n_prompt: int = 512,
    model_path: Optional[str] = None,
) -> BenchmarkResult:
    """
    llama-bench를 사용한 공식 벤치마크

    Prompt Processing (pp) + Token Generation (tg) 모두 측정합니다.
    """
    model = model_path or str(get_model_path())

    if not LLAMA_BENCH.exists():
        raise FileNotFoundError(f"llama-bench 바이너리를 찾을 수 없습니다: {LLAMA_BENCH}")

    command = [
        str(LLAMA_BENCH),
        "-m", model,
        "-n", str(n_tokens),
        "-ngl", "0",
        "-b", "1",
        "-t", str(threads),
        "-p", str(n_prompt),
        "-r", "3",  # 3회 반복
    ]

    print(f"\n{'='*60}")
    print(f"  llama-bench 공식 벤치마크")
    print(f"  Threads: {threads} | Gen: {n_tokens} tokens | Prompt: {n_prompt} tokens")
    print(f"{'='*60}")

    resource_results = {"avg_cpu_percent": 0.0, "peak_memory_mb": 0.0}

    start_time = time.time()
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=_monitor_resources,
        args=(proc.pid, stop_event, resource_results),
        daemon=True,
    )
    monitor_thread.start()

    stdout, stderr = proc.communicate(timeout=600)
    elapsed = time.time() - start_time

    stop_event.set()
    monitor_thread.join(timeout=2)

    stdout_text = stdout.decode("utf-8", errors="replace")
    print(stdout_text)

    # llama-bench 출력에서 tg(token generation) 속도 파싱
    tps = 0.0
    for line in stdout_text.split("\n"):
        if "tg" in line:
            try:
                parts = line.strip().split()
                # 마지막 숫자가 보통 tok/s
                for part in reversed(parts):
                    try:
                        tps = float(part)
                        if tps > 0:
                            break
                    except ValueError:
                        continue
            except (ValueError, IndexError):
                pass

    result = BenchmarkResult(
        test_name="llama-bench",
        threads=threads,
        n_tokens=n_tokens,
        n_prompt=n_prompt,
        elapsed_seconds=round(elapsed, 3),
        tokens_per_second=round(tps, 2),
        avg_cpu_percent=round(resource_results["avg_cpu_percent"], 1),
        peak_memory_mb=round(resource_results["peak_memory_mb"], 1),
        model=os.path.basename(model),
    )

    _print_result(result)
    return result


def _print_result(result: BenchmarkResult):
    """벤치마크 결과 출력"""
    print(f"\n--- 결과 ({result.test_name}) ---")
    print(f"  모델:           {result.model}")
    print(f"  스레드 수:      {result.threads}")
    print(f"  생성 토큰:      {result.n_tokens}")
    print(f"  총 소요 시간:   {result.elapsed_seconds:.3f}초")
    print(f"  토큰 생성 속도: {result.tokens_per_second:.2f} tok/s")
    print(f"  평균 CPU 사용:  {result.avg_cpu_percent:.1f}%")
    print(f"  피크 메모리:    {result.peak_memory_mb:.1f} MB")
    print()


def run_full_benchmark(
    thread_counts: List[int],
    token_counts: List[int],
    use_llama_bench: bool = False,
    model_path: Optional[str] = None,
) -> List[BenchmarkResult]:
    """
    다양한 스레드/토큰 조합으로 전체 벤치마크 실행

    Args:
        thread_counts: 테스트할 스레드 수 리스트
        token_counts: 테스트할 토큰 수 리스트
        use_llama_bench: True면 llama-bench 사용, False면 직접 추론
        model_path: 모델 경로

    Returns:
        벤치마크 결과 리스트
    """
    if not is_binary_available():
        print("ERROR: bitnet.cpp 바이너리가 빌드되지 않았습니다.")
        print("  빌드 명령: bash bitnet/setup.sh --build-only")
        sys.exit(1)

    if not is_model_available():
        print("ERROR: BitNet 모델이 다운로드되지 않았습니다.")
        print("  다운로드 명령: bash bitnet/setup.sh --download-only")
        sys.exit(1)

    results = []

    print("\n" + "=" * 70)
    print("  BitNet b1.58 - CPU 기반 1-bit LLM 벤치마크")
    print("  모델: BitNet-b1.58-2B-4T (2.4B params, 1.58-bit)")
    print(f"  CPU 코어: {os.cpu_count()}")
    print("=" * 70)

    for threads in thread_counts:
        for n_tokens in token_counts:
            try:
                if use_llama_bench:
                    result = run_llama_bench(
                        threads=threads,
                        n_tokens=n_tokens,
                        model_path=model_path,
                    )
                else:
                    result = run_inference_benchmark(
                        threads=threads,
                        n_tokens=n_tokens,
                        model_path=model_path,
                    )
                results.append(result)
            except Exception as e:
                print(f"  ERROR: threads={threads}, tokens={n_tokens}: {e}")

    # 종합 결과 출력
    _print_summary(results)
    return results


def _print_summary(results: List[BenchmarkResult]):
    """전체 벤치마크 결과 요약 테이블 출력"""
    if not results:
        return

    print("\n" + "=" * 80)
    print("  벤치마크 종합 결과")
    print("=" * 80)
    print(f"{'Test':<15} {'Threads':>8} {'Tokens':>8} {'Time(s)':>10} {'Tok/s':>10} {'CPU%':>8} {'Mem(MB)':>10}")
    print("-" * 80)

    for r in results:
        print(
            f"{r.test_name:<15} {r.threads:>8} {r.n_tokens:>8} "
            f"{r.elapsed_seconds:>10.3f} {r.tokens_per_second:>10.2f} "
            f"{r.avg_cpu_percent:>8.1f} {r.peak_memory_mb:>10.1f}"
        )

    print("-" * 80)

    # 최고 성능 하이라이트
    if results:
        best = max(results, key=lambda r: r.tokens_per_second)
        print(f"\n  최고 성능: {best.tokens_per_second:.2f} tok/s "
              f"(threads={best.threads}, tokens={best.n_tokens})")

    # JSON 저장
    output_path = "bitnet/benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="BitNet b1.58 벤치마크 - CPU 점유율 대비 토큰 생성 속도 측정"
    )
    parser.add_argument(
        "--threads", "-t",
        type=int, nargs="+",
        default=[2, 4, 8],
        help="테스트할 스레드 수 (여러 개 지정 가능)",
    )
    parser.add_argument(
        "--n-tokens", "-n",
        type=int, nargs="+",
        default=[64, 128],
        help="생성할 토큰 수 (여러 개 지정 가능)",
    )
    parser.add_argument(
        "--use-llama-bench",
        action="store_true",
        help="llama-bench 바이너리 사용 (공식 벤치마크)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="모델 경로 (기본값: 설정 파일 참조)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="JSON 결과 출력 경로",
    )

    args = parser.parse_args()

    results = run_full_benchmark(
        thread_counts=args.threads,
        token_counts=args.n_tokens,
        use_llama_bench=args.use_llama_bench,
        model_path=args.model,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
        print(f"결과 저장: {args.output}")


if __name__ == "__main__":
    main()
