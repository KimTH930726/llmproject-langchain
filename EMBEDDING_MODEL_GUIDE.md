# 임베딩 모델 가이드 (FastEmbed)

## 개요

**현재 시스템**: FastEmbed (Qdrant 경량 임베딩 라이브러리)
- ONNX Runtime 기반 (PyTorch 불필요)
- Backend 이미지 크기: 778MB (sentence-transformers 7.97GB 대비 90% 감소)
- 기본 모델: `paraphrase-multilingual-mpnet-base-v2` (768차원, 다국어)

---

## 지원 모델 목록

### FastEmbed 다국어 모델

| 모델 이름 | 벡터 차원 | 언어 지원 | 용도 |
|----------|----------|---------|------|
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | **기본 설정**, 한국어 포함 | 범용 |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 한국어 포함, 경량 | 빠른 처리 |
| `intfloat/multilingual-e5-large` | 1024 | 한국어 포함, 고성능 | 정확도 우선 |

**참고**: FastEmbed는 한국어 전용 모델은 지원하지 않지만, 다국어 모델이 한국어를 포함합니다.

---

## 모델 변경 방법

### 1단계: 환경 변수 수정

`backend/.env`:
```bash
# 기본 (현재 설정)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2

# 경량 모델 (384차원)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# 고성능 모델 (1024차원)
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

**주의**: FastEmbed는 공식 모델 이름을 사용합니다 (`sentence-transformers/` 프리픽스 포함).

### 2단계: qdrant_service.py 수정

모델 변경 시 벡터 크기도 수정 필요:
```python
# backend/app/services/qdrant_service.py

self.vector_size = 768   # mpnet-base-v2
# self.vector_size = 384  # MiniLM-L6-v2
# self.vector_size = 1024 # e5-large
```

### 3단계: 컬렉션 재생성

**벡터 차원이 변경되면 기존 컬렉션 삭제 필수**:
```bash
# Qdrant 컬렉션 삭제
curl -X DELETE http://localhost:6333/collections/documents

# Backend 재시작 (컬렉션 자동 생성)
docker-compose restart backend

# 기존 문서 재업로드 필요
```

---

## 벡터 차원 확인

### Backend API 사용
```bash
curl http://localhost:8000/api/upload/stats
```

### Qdrant API 사용
```bash
curl http://localhost:6333/collections/documents
```

응답 예시:
```json
{
  "result": {
    "vectors": {"size": 768, "distance": "Cosine"}
  }
}
```

---

## Qdrant 벡터 DB 설정 변경

### 1. 컬렉션 이름 변경

#### Step 1: 환경 변수 수정

```bash
# backend/.env
QDRANT_COLLECTION_NAME=my_custom_collection
```

#### Step 2: Backend 재시작

```bash
docker-compose restart backend
```

새로운 컬렉션이 자동으로 생성됩니다.

### 2. 유사도 측정 방식 변경

현재는 **Cosine 유사도**를 사용하지만, 다른 방식으로 변경 가능합니다.

#### 사용 가능한 Distance 타입

| Distance | 설명 | 사용 시기 |
|----------|------|-----------|
| `Cosine` | 코사인 유사도 (기본값) | 일반적인 텍스트 검색 |
| `Dot` | 내적 (Dot Product) | 정규화된 벡터 사용 시 |
| `Euclidean` | 유클리드 거리 | 절대 거리 중요 시 |

#### 변경 방법

`backend/app/services/qdrant_service.py` 파일 수정:

```python
from qdrant_client.models import Distance, VectorParams

# 기존 (Cosine)
self.client.create_collection(
    collection_name=self.collection_name,
    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
)

# Euclidean으로 변경
self.client.create_collection(
    collection_name=self.collection_name,
    vectors_config=VectorParams(size=self.vector_size, distance=Distance.EUCLIDEAN),
)

# Dot Product로 변경
self.client.create_collection(
    collection_name=self.collection_name,
    vectors_config=VectorParams(size=self.vector_size, distance=Distance.DOT),
)
```

**변경 후**:
1. 코드 수정
2. 기존 컬렉션 삭제
3. Backend 재시작
4. 문서 재업로드

---

## 고급 설정

### 1. 검색 결과 개수 조정

#### RAG 서비스에서 Top-K 변경

`backend/app/services/rag_service.py`:

```python
async def answer_question(self, question: str, top_k: int = 3) -> Dict[str, Any]:
    # top_k 기본값 변경
    # 3 → 5로 변경하면 더 많은 문서 참조
```

#### API 호출 시 동적 지정

```bash
# 현재는 코드에서 고정값 사용
# 향후 개선: API에서 파라미터로 받기
```

### 2. 임베딩 모델 로컬 캐시 위치

Sentence Transformers는 모델을 자동으로 다운로드하여 캐시합니다.

**캐시 위치**:
- Linux/Mac: `~/.cache/torch/sentence_transformers/`
- Windows: `C:\Users\<username>\.cache\torch\sentence_transformers\`

**폐쇄망 배포 시 모델 미리 준비**:

```bash
# 인터넷 환경에서
python3 << EOF
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('jhgan/ko-sroberta-multitask')
print("Model downloaded to:", model._model_card_vars.get('model_name', 'Unknown'))
EOF

# 캐시 디렉토리 압축
tar -czf sentence_transformers_cache.tar.gz ~/.cache/torch/sentence_transformers/

# 서버에서 압축 해제
tar -xzf sentence_transformers_cache.tar.gz -C ~/
```

### 3. Qdrant 스토리지 위치 변경

Docker Compose에서 볼륨 마운트 위치 변경:

```yaml
# docker-compose.yml (예시, 현재는 Qdrant가 별도 실행 중)
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage  # 여기 경로 변경
```

또는 직접 실행 시:

```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -v /custom/path/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

---

## 벡터 검색 성능 최적화

### 1. 인덱스 파라미터 조정

Qdrant는 기본적으로 HNSW (Hierarchical Navigable Small World) 인덱스를 사용합니다.

`backend/app/services/qdrant_service.py`에서 설정:

```python
from qdrant_client.models import VectorParams, Distance, HnswConfigDiff

self.client.create_collection(
    collection_name=self.collection_name,
    vectors_config=VectorParams(
        size=self.vector_size,
        distance=Distance.COSINE,
        hnsw_config=HnswConfigDiff(
            m=16,              # 기본값: 16, 높이면 정확도↑ 메모리↑
            ef_construct=100,  # 기본값: 100, 높이면 빌드 느림, 검색 빠름
        )
    ),
)
```

### 2. 검색 정확도 vs 속도 조절

```python
# qdrant_service.py의 search 메서드
search_result = self.client.search(
    collection_name=self.collection_name,
    query_vector=query_vector,
    limit=limit,
    search_params={"hnsw_ef": 128}  # 기본 없음, 높이면 정확도↑ 속도↓
)
```

---

## 모델별 성능 비교 (참고)

| 모델 | 벡터 차원 | 검색 속도 | 정확도 | 메모리 사용 |
|------|----------|----------|--------|------------|
| MiniLM-L12 (384) | 384 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ko-sroberta (768) | 768 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| mpnet-base (768) | 768 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| e5-large (1024) | 1024 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

**추천**:
- **일반 문서 검색**: `jhgan/ko-sroberta-multitask` (기본값)
- **빠른 응답 필요**: `paraphrase-multilingual-MiniLM-L12-v2`
- **최고 정확도 필요**: `intfloat/multilingual-e5-large`

---

## 문제 해결

### Q1: 모델 변경 후 검색 결과가 없음

**원인**: 기존 벡터와 차원이 달라서 검색 불가

**해결**:
```bash
# 1. 컬렉션 삭제
curl -X DELETE http://localhost:6333/collections/documents

# 2. Backend 재시작 (컬렉션 자동 재생성)
docker-compose restart backend

# 3. 문서 재업로드
```

### Q2: "Model not found" 에러

**원인**: 모델 이름 오타 또는 존재하지 않는 모델

**해결**:
- Hugging Face에서 모델 이름 확인: https://huggingface.co/models?library=sentence-transformers
- 정확한 모델 이름 사용

### Q3: 메모리 부족 에러

**원인**: 대형 모델 (e5-large 등) 사용 시 메모리 부족

**해결**:
```bash
# 더 작은 모델로 변경
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### Q4: 검색 속도가 느림

**원인**: 너무 많은 문서 또는 큰 벡터 차원

**해결**:
1. 작은 차원 모델 사용 (384차원)
2. HNSW 파라미터 조정 (`hnsw_ef` 낮추기)
3. Top-K 결과 개수 줄이기

---

## 변경 체크리스트

임베딩 모델을 변경할 때 다음 체크리스트를 따르세요:

- [ ] `.env` 파일에 새 모델 이름 설정
- [ ] 새 모델의 벡터 차원 확인
- [ ] 기존 Qdrant 컬렉션 삭제
- [ ] Backend 재시작
- [ ] 컬렉션이 올바른 벡터 차원으로 생성되었는지 확인
- [ ] 모든 문서 재업로드
- [ ] 검색 테스트 수행
- [ ] 성능 및 정확도 확인

---

## 참고 자료

- Sentence Transformers 문서: https://www.sbert.net/
- Qdrant 문서: https://qdrant.tech/documentation/
- Hugging Face 모델 허브: https://huggingface.co/models?library=sentence-transformers&language=ko
