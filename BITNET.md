# BitNet b1.58 - CPU 기반 로컬 LLM 구축 가이드

## 개요

**BitNet b1.58**은 Microsoft Research가 개발한 1-bit (정확히는 1.58-bit) Large Language Model입니다.
가중치를 삼진값(ternary: {-1, 0, +1})으로 양자화하여, 기존 FP16 모델 대비 **메모리 사용량 10배 이상 감소**,
**CPU에서도 실용적인 추론 속도**를 달성합니다.

### 핵심 수치

| 항목 | 값 |
|------|-----|
| 모델 | BitNet-b1.58-2B-4T |
| 파라미터 | 2.4B |
| 양자화 | 1.58-bit (삼진값) |
| GGUF 크기 | ~1.19 GB |
| 학습 데이터 | 4조 토큰 |
| 컨텍스트 길이 | 4096 토큰 |
| 라이선스 | MIT |

### 왜 1-bit LLM인가?

1. **메모리 효율**: 2B 파라미터 모델이 1.19GB로 압축 (FP16 대비 ~3.4x)
2. **CPU 추론**: GPU 없이 일반 PC에서 실행 가능
3. **에너지 절약**: x86 CPU에서 71.9%~82.2% 에너지 소비 감소
4. **속도**: x86에서 2.37x~6.17x 속도 향상 (FP16 대비)
5. **Native 양자화**: 사후 양자화가 아닌, 처음부터 1.58-bit로 학습

---

## 프로젝트 구조

```
llmproject-langchain/
├── bitnet/                        # BitNet Python 모듈
│   ├── __init__.py
│   ├── config.py                  # 설정 관리 (경로, 기본값)
│   ├── bitnet_runner.py           # bitnet.cpp 래퍼 (추론 실행)
│   ├── benchmark.py               # CPU 벤치마크 (tok/s, CPU%, 메모리)
│   └── setup.sh                   # 원클릭 빌드/다운로드 스크립트
├── bitnet-cpp/                    # Microsoft bitnet.cpp (git clone)
│   ├── build/bin/                 # 빌드된 바이너리
│   │   ├── llama-cli              # CLI 추론
│   │   ├── llama-server           # HTTP 서버 (OpenAI 호환)
│   │   ├── llama-bench            # 공식 벤치마크
│   │   └── llama-quantize         # 양자화 도구
│   └── models/BitNet-b1.58-2B-4T/ # 모델 디렉토리
│       └── ggml-model-i2_s.gguf   # GGUF 모델 파일
├── backend/app/
│   ├── services/bitnet_service.py # FastAPI 통합 서비스
│   ├── api/bitnet.py              # REST API 엔드포인트
│   └── main.py                    # BitNet 라우터 등록
└── BITNET.md                      # 이 문서
```

---

## 빠른 시작

### 1. 전체 설치 (빌드 + 모델 다운로드)

```bash
bash bitnet/setup.sh
```

### 2. 빌드만 (모델은 나중에)

```bash
bash bitnet/setup.sh --build-only
```

### 3. 모델 다운로드만

```bash
# 자동 다운로드 (HuggingFace CLI)
bash bitnet/setup.sh --download-only

# 수동 다운로드 (폐쇄망/프록시 환경)
# 1. https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf 접속
# 2. ggml-model-i2_s.gguf (~1.19 GB) 다운로드
# 3. bitnet-cpp/models/BitNet-b1.58-2B-4T/ 에 복사
```

### 4. 상태 확인

```bash
bash bitnet/setup.sh --status
```

---

## 사용 방법

### CLI 직접 추론

```bash
# bitnet.cpp 원본 스크립트
cd bitnet-cpp
python run_inference.py \
  -m models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf \
  -p "한국의 수도는 어디인가요?" \
  -n 128 -t 4
```

### Python 래퍼

```python
from bitnet.bitnet_runner import get_bitnet_runner

runner = get_bitnet_runner()

# 기본 추론
result = runner.generate("인공지능의 미래에 대해 설명해 주세요.")
print(result.text)
print(f"속도: {result.tokens_per_second:.2f} tok/s")
print(f"시간: {result.elapsed_seconds:.2f}초")

# 설정 변경
runner = BitNetRunner(threads=8, n_predict=512, temperature=0.5)
result = runner.generate("양자 컴퓨팅에 대해 설명해 주세요.")
```

### 벤치마크 실행

```bash
# 기본 벤치마크 (threads: 2,4,8 / tokens: 64,128)
python -m bitnet.benchmark

# 커스텀 벤치마크
python -m bitnet.benchmark --threads 1 2 4 8 16 --n-tokens 64 128 256

# llama-bench 공식 벤치마크
python -m bitnet.benchmark --use-llama-bench --threads 4 8
```

### FastAPI 엔드포인트

```bash
# 서버 실행
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 상태 확인
curl http://localhost:8000/api/bitnet/status | python -m json.tool

# 텍스트 생성
curl -X POST http://localhost:8000/api/bitnet/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "한국의 수도는?", "n_predict": 128}'

# 채팅
curl -X POST http://localhost:8000/api/bitnet/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "BitNet이란 무엇인가요?"}'
```

---

## 빌드 상세

### 사전 요구 사항

| 도구 | 최소 버전 |
|------|-----------|
| CMake | 3.22+ |
| Clang | 18+ |
| Python | 3.9+ |

### 빌드 과정

bitnet.cpp 빌드는 3단계로 진행됩니다:

1. **커널 코드 생성**: 모델 아키텍처에 맞는 최적화된 LUT(Lookup Table) 커널 생성
   - x86_64: `codegen_tl2.py` (TL2 커널)
   - ARM64: `codegen_tl1.py` (TL1 커널)

2. **CMake 빌드**: clang으로 C++ 소스 컴파일
   - ggml 백엔드 (bitnet-mad, bitnet-lut 커널 포함)
   - llama.cpp 메인 라이브러리
   - CLI, Server, Bench 등 실행 파일

3. **모델 변환** (GGUF 직접 다운로드 시 불필요):
   - HF safetensors → GGUF f32 → i2_s 양자화

### 알려진 이슈

- **const 불일치 경고**: `ggml-bitnet-mad.cpp`에서 `int8_t * y_col` 선언이
  const 소스를 참조하는 문제. `const int8_t *`로 수정 필요. (`setup.sh`에서 자동 처리)
- **OpenMP 미설치**: 빌드 경고 발생하지만 동작에 영향 없음.
  설치 시 멀티스레드 GEMM 성능 향상 가능.

---

## 아키텍처 설계

### 기존 시스템과의 관계

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI Backend                     │
├──────────────┬──────────────┬───────────────────────┤
│  /api/chat/  │ /api/upload/ │    /api/bitnet/        │
│  (LangGraph  │  (문서 업로드) │  (BitNet CPU 추론)      │
│   + Ollama)  │              │                        │
├──────────────┴──────────────┴───────────────────────┤
│              Services Layer                           │
├──────────┬──────────┬───────────────────────────────┤
│ Ollama   │ Qdrant   │     BitNet Service              │
│ Service  │ Service  │  (subprocess → llama-cli)       │
├──────────┴──────────┴───────────────────────────────┤
│           Infrastructure                              │
├──────────┬──────────┬───────────────────────────────┤
│ Ollama   │ Qdrant   │     bitnet.cpp                  │
│ (GPU/CPU)│ (Vector) │  (CPU-only, 1.58-bit)          │
└──────────┴──────────┴───────────────────────────────┘
```

### 설계 원칙

1. **독립적 모듈**: BitNet은 기존 Ollama 기반 시스템과 독립적으로 운영
2. **동일한 패턴**: 싱글톤 + Lazy Init 패턴으로 기존 서비스와 일관성 유지
3. **Subprocess 기반**: bitnet.cpp 바이너리를 직접 호출하여 최적 성능 확보
4. **점진적 통합**: 향후 Agent의 Tool로 등록하여 LLM이 자동 선택 가능

---

## 성능 기대치

### BitNet b1.58 vs Ollama llama3.2:1b

| 항목 | BitNet b1.58-2B | Ollama llama3.2:1b |
|------|-----------------|-------------------|
| 파라미터 | 2.4B | 1.2B |
| 양자화 | 1.58-bit (native) | FP16/Q4 |
| 모델 크기 | 1.19 GB | ~700 MB (Q4) |
| 추론 방식 | CPU 전용 (최적화) | CPU/GPU |
| 기대 속도 | 5-15 tok/s (CPU) | 10-30 tok/s (CPU) |
| 에너지 효율 | 70-80% 절감 | 기준선 |
| 컨텍스트 | 4096 | 2048 |

### 벤치마크 측정 항목

- **토큰 생성 속도** (tok/s): 초당 생성 토큰 수
- **CPU 점유율** (%): 추론 중 평균 CPU 사용률
- **메모리 사용량** (MB): 피크 RSS 메모리
- **에너지 효율**: tok/s per CPU%

---

## 학습 포인트

이 실습을 통해 학습할 수 있는 핵심 개념:

1. **1-bit 양자화 원리**: 가중치를 {-1, 0, +1}로 표현하는 삼진 양자화
2. **LUT 커널 최적화**: 곱셈 대신 테이블 룩업으로 행렬 연산 가속
3. **GGUF 포맷**: llama.cpp 생태계의 표준 모델 포맷
4. **CPU SIMD 활용**: x86 AVX2/AVX-512 또는 ARM NEON 벡터 연산
5. **Native vs Post-training 양자화**: 학습 시 양자화 vs 학습 후 양자화의 차이
6. **Subprocess 기반 서비스 통합**: Python ↔ C++ 바이너리 연동 패턴

---

## 참고 자료

- [Microsoft BitNet 공식 저장소](https://github.com/microsoft/BitNet)
- [BitNet b1.58-2B-4T 모델 (HuggingFace)](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T)
- [GGUF 모델 (HuggingFace)](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf)
- [BitNet: Scaling 1-bit Transformers (논문)](https://arxiv.org/abs/2310.11453)
- [The Era of 1-bit LLMs (논문)](https://arxiv.org/abs/2402.17764)
