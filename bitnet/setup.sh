#!/usr/bin/env bash
#
# BitNet b1.58 - 원클릭 설치/빌드/다운로드 스크립트
#
# Usage:
#   bash bitnet/setup.sh              # 전체 설치 (클론 + 빌드 + 모델 다운로드)
#   bash bitnet/setup.sh --build-only  # 빌드만
#   bash bitnet/setup.sh --download-only # 모델 다운로드만
#   bash bitnet/setup.sh --status      # 상태 확인
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BITNET_CPP_DIR="$PROJECT_ROOT/bitnet-cpp"
MODELS_DIR="$BITNET_CPP_DIR/models/BitNet-b1.58-2B-4T"
GGUF_MODEL="$MODELS_DIR/ggml-model-i2_s.gguf"

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 상태 확인
# ============================================================
check_status() {
    echo ""
    echo "============================================"
    echo "  BitNet b1.58 환경 상태"
    echo "============================================"

    # 시스템 정보
    echo ""
    echo "시스템 정보:"
    echo "  OS:     $(uname -s) $(uname -m)"
    echo "  CPU:    $(nproc) cores"
    echo "  Memory: $(free -h | awk '/Mem:/ {print $2}')"
    echo ""

    # 빌드 도구
    echo "빌드 도구:"
    cmake --version 2>/dev/null | head -1 && echo "  cmake: OK" || echo "  cmake: NOT FOUND"
    clang++ --version 2>/dev/null | head -1 && echo "  clang++: OK" || echo "  clang++: NOT FOUND"
    python3 --version 2>/dev/null && echo "  python3: OK" || echo "  python3: NOT FOUND"
    echo ""

    # bitnet.cpp
    echo "bitnet.cpp:"
    if [ -d "$BITNET_CPP_DIR" ]; then
        log_ok "소스 클론됨: $BITNET_CPP_DIR"
    else
        log_warn "소스 미존재"
    fi

    if [ -f "$BITNET_CPP_DIR/build/bin/llama-cli" ]; then
        log_ok "바이너리 빌드됨"
        ls -lh "$BITNET_CPP_DIR/build/bin/llama-cli" | awk '{print "  크기: "$5}'
    else
        log_warn "바이너리 미빌드"
    fi
    echo ""

    # 모델
    echo "모델:"
    if [ -f "$GGUF_MODEL" ]; then
        log_ok "GGUF 모델 존재"
        ls -lh "$GGUF_MODEL" | awk '{print "  크기: "$5}'
    else
        log_warn "GGUF 모델 미다운로드"
        echo "  경로: $GGUF_MODEL"
    fi
    echo ""
}

# ============================================================
# 1. 소스 클론
# ============================================================
clone_repo() {
    if [ -d "$BITNET_CPP_DIR" ]; then
        log_ok "bitnet.cpp 이미 존재, 건너뜁니다."
        return
    fi

    log_info "bitnet.cpp 클론 중..."
    git clone --recursive https://github.com/microsoft/BitNet.git "$BITNET_CPP_DIR"
    log_ok "클론 완료"
}

# ============================================================
# 2. 의존성 설치
# ============================================================
install_deps() {
    log_info "Python 의존성 설치 중..."
    pip install numpy sentencepiece "transformers>=4.46.3" "gguf>=0.1.0" protobuf 2>/dev/null || true

    # gguf 로컬 패키지 설치
    if [ -d "$BITNET_CPP_DIR/3rdparty/llama.cpp/gguf-py" ]; then
        pip install "$BITNET_CPP_DIR/3rdparty/llama.cpp/gguf-py" 2>/dev/null || true
    fi

    log_ok "의존성 설치 완료"
}

# ============================================================
# 3. 커널 코드 생성 + 빌드
# ============================================================
build_bitnet() {
    if [ ! -d "$BITNET_CPP_DIR" ]; then
        log_error "bitnet.cpp 소스가 없습니다. 먼저 클론하세요."
        exit 1
    fi

    cd "$BITNET_CPP_DIR"

    ARCH=$(uname -m)
    log_info "아키텍처 감지: $ARCH"

    # 커널 코드 생성
    log_info "최적화 커널 코드 생성 중 (BitNet-b1.58-2B-4T)..."
    if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "AMD64" ]; then
        python3 utils/codegen_tl2.py \
            --model bitnet_b1_58-3B \
            --BM 160,320,320 \
            --BK 96,96,96 \
            --bm 32,32,32
        CMAKE_EXTRA="-DBITNET_X86_TL2=OFF"
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        python3 utils/codegen_tl1.py \
            --model bitnet_b1_58-3B \
            --BM 160,320,320 \
            --BK 64,128,64 \
            --bm 32,64,32
        CMAKE_EXTRA="-DBITNET_ARM_TL1=OFF"
    else
        log_error "지원하지 않는 아키텍처: $ARCH"
        exit 1
    fi

    # CMake 구성
    log_info "CMake 구성 중..."
    cmake -B build \
        $CMAKE_EXTRA \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++

    # 빌드
    log_info "컴파일 중 ($(nproc) cores)..."
    cmake --build build --config Release -j$(nproc)

    # const 수정 (알려진 이슈)
    if [ $? -ne 0 ]; then
        log_warn "const 호환성 패치 적용 중..."
        sed -i 's/int8_t \* y_col = y + col \* by;/const int8_t * y_col = y + col * by;/' \
            src/ggml-bitnet-mad.cpp
        cmake --build build --config Release -j$(nproc)
    fi

    log_ok "빌드 완료"
    ls -lh build/bin/llama-cli build/bin/llama-server build/bin/llama-bench 2>/dev/null

    cd "$PROJECT_ROOT"
}

# ============================================================
# 4. 모델 다운로드
# ============================================================
download_model() {
    mkdir -p "$MODELS_DIR"

    if [ -f "$GGUF_MODEL" ] && [ -s "$GGUF_MODEL" ]; then
        log_ok "GGUF 모델이 이미 존재합니다."
        ls -lh "$GGUF_MODEL"
        return
    fi

    log_info "BitNet-b1.58-2B-4T GGUF 모델 다운로드 중..."
    log_info "HuggingFace 저장소: microsoft/BitNet-b1.58-2B-4T-gguf"

    # huggingface-cli 사용
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download microsoft/BitNet-b1.58-2B-4T-gguf \
            --local-dir "$MODELS_DIR" || {
            log_error "HuggingFace 다운로드 실패 (네트워크/프록시 문제일 수 있음)"
            log_info ""
            log_info "수동 다운로드 방법:"
            log_info "  1. https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf 접속"
            log_info "  2. ggml-model-i2_s.gguf 파일 다운로드 (~1.19 GB)"
            log_info "  3. 파일을 다음 경로에 복사:"
            log_info "     $GGUF_MODEL"
            return 1
        }
    else
        log_error "huggingface-cli가 설치되지 않았습니다."
        log_info "  pip install huggingface_hub"
        return 1
    fi

    log_ok "모델 다운로드 완료"
    ls -lh "$GGUF_MODEL"
}

# ============================================================
# 5. 검증
# ============================================================
verify_setup() {
    echo ""
    echo "============================================"
    echo "  설치 검증"
    echo "============================================"

    PASS=true

    if [ -f "$BITNET_CPP_DIR/build/bin/llama-cli" ]; then
        log_ok "llama-cli 바이너리"
    else
        log_error "llama-cli 바이너리 없음"
        PASS=false
    fi

    if [ -f "$BITNET_CPP_DIR/build/bin/llama-server" ]; then
        log_ok "llama-server 바이너리"
    else
        log_error "llama-server 바이너리 없음"
        PASS=false
    fi

    if [ -f "$GGUF_MODEL" ] && [ -s "$GGUF_MODEL" ]; then
        log_ok "GGUF 모델 ($(ls -lh "$GGUF_MODEL" | awk '{print $5}'))"
    else
        log_warn "GGUF 모델 미다운로드 (추론 실행 불가)"
        PASS=false
    fi

    echo ""
    if [ "$PASS" = true ]; then
        log_ok "모든 검증 통과!"
        echo ""
        echo "사용 방법:"
        echo "  # 추론 실행"
        echo "  python -m bitnet.bitnet_runner '한국의 수도는?'"
        echo ""
        echo "  # 벤치마크"
        echo "  python -m bitnet.benchmark --threads 2 4 8 --n-tokens 64 128"
        echo ""
        echo "  # FastAPI 서버 (기존 프로젝트 통합)"
        echo "  curl http://localhost:8000/api/bitnet/generate -d '{\"prompt\": \"Hello\"}'"
    else
        log_warn "일부 항목이 누락되어 있습니다."
    fi
    echo ""
}

# ============================================================
# 메인 실행
# ============================================================
case "${1:-full}" in
    --status)
        check_status
        ;;
    --build-only)
        install_deps
        build_bitnet
        ;;
    --download-only)
        download_model
        ;;
    --verify)
        verify_setup
        ;;
    full|--full)
        log_info "BitNet b1.58 전체 설치 시작"
        clone_repo
        install_deps
        build_bitnet
        download_model
        verify_setup
        ;;
    *)
        echo "Usage: $0 [--full|--build-only|--download-only|--status|--verify]"
        exit 1
        ;;
esac
