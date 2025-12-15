# RAG 기능 구현 완료 보고서

## 구현 개요

흐름도에 따라 RAG (Retrieval-Augmented Generation) 기반 문서 검색 및 자연어 SQL 기능을 기존 프로젝트에 통합했습니다.

### 주요 특징
- 기존 코드 구조 유지 (backward compatible)
- 서비스 레이어 캡슐화로 유지보수성 확보
- 싱글톤 패턴으로 리소스 효율적 관리
- QueryRouter를 통한 자동 의도 분류

---

## 구현된 기능

### 1. 문서 업로드 및 벡터 저장
**파일**: `backend/app/api/upload.py`, `backend/app/utils/text_extractor.py`

**기능**:
- PDF, DOCX, TXT, XLSX 파일에서 텍스트 추출
- Sentence Transformer로 임베딩 (한국어 모델: jhgan/ko-sroberta-multitask)
- Qdrant 벡터 DB에 저장

**API**:
```http
POST /api/upload/
GET /api/upload/stats
```

### 2. RAG 기반 문서 검색
**파일**: `backend/app/services/rag_service.py`, `backend/app/services/qdrant_service.py`

**기능**:
- 사용자 질문을 임베딩하여 Qdrant에서 유사 문서 검색 (코사인 유사도)
- Top-K 문서를 컨텍스트로 사용
- Ollama LLM으로 답변 생성 (문서 기반)

### 3. 자연어 SQL 쿼리
**파일**: `backend/app/services/sql_agent.py`

**기능**:
- 자연어 질의를 SQL로 변환 (LLM 사용)
- PostgreSQL 데이터베이스 조회
- 결과를 자연어로 해석하여 답변

**보안**: 제한적 SQL 실행 (SELECT만, 패턴 검증)

### 4. QueryRouter (의도 분류)
**파일**: `backend/app/services/query_router.py`

**기능**:
- 사용자 질의의 의도를 자동 분류
  - `rag_search`: 문서 내용 검색
  - `sql_query`: 데이터베이스 조회
  - `general`: 일반 대화
- 규칙 기반 (빠름) + LLM 기반 (정확) 두 가지 방식 제공

### 5. 통합 채팅 API
**파일**: `backend/app/api/chat.py`

**기능**:
- QueryRouter로 의도 자동 분류
- 의도별 적절한 서비스 호출 (RAG / SQL Agent / Ollama)
- 통합 응답 포맷 반환

**API**:
```http
POST /api/chat/
POST /api/chat/classify (디버깅용)
```

---

## 프로젝트 구조 변경 사항

### 신규 파일
```
backend/app/
├── api/
│   ├── chat.py              ← 신규
│   └── upload.py            ← 신규
├── models/
│   └── chat.py              ← 신규
├── services/
│   ├── qdrant_service.py    ← 신규
│   ├── rag_service.py       ← 신규
│   ├── query_router.py      ← 신규
│   └── sql_agent.py         ← 신규
└── utils/
    └── text_extractor.py    ← 신규
```

### 수정된 파일
- `backend/app/main.py`: 신규 라우터 등록
- `backend/app/models/applicant.py`: SQLAlchemy 컬럼 매핑 개선
- `backend/app/api/analysis.py`: 디버그 로깅 추가
- `backend/requirements.txt`: RAG 패키지 추가
- `backend/.env.example`: Qdrant, 임베딩 모델 설정 추가
- `CLAUDE.md`: RAG 기능 문서화

---

## 의존성 추가

`requirements.txt`에 추가된 패키지:
```
qdrant-client==1.7.0           # 벡터 DB 클라이언트
sentence-transformers==2.3.1   # 임베딩 모델
python-multipart==0.0.6        # 파일 업로드
PyPDF2==3.0.1                  # PDF 텍스트 추출
python-docx==1.1.0             # DOCX 텍스트 추출
openpyxl==3.1.2                # XLSX 텍스트 추출
```

---

## 환경 변수 설정

`.env` 파일에 추가 필요:
```bash
# Qdrant 설정
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=documents

# 임베딩 모델 (한국어 지원)
EMBEDDING_MODEL=jhgan/ko-sroberta-multitask
```

---

## 배포 전제 조건 (서버)

기존 요구사항:
- PostgreSQL (Docker)
- Ollama (Docker, llama3.2:1b 모델)

**신규 요구사항**:
- **Qdrant** (Docker, 벡터 DB)

### Qdrant 설치
```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

---

## API 사용 예시

### 1. 문서 업로드
```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@document.pdf"
```

**응답**:
```json
{
  "message": "파일이 성공적으로 업로드되었습니다",
  "filename": "document.pdf",
  "doc_id": "a1b2c3d4e5f6...",
  "text_length": 1523
}
```

### 2. RAG 채팅
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "계약서에 명시된 금액은?"}'
```

**응답**:
```json
{
  "answer": "계약서에 명시된 금액은 1,000,000원입니다.",
  "intent": "rag_search",
  "sources": [
    {
      "text": "본 계약의 총 금액은 일금 1,000,000원으로 한다...",
      "score": 0.89,
      "metadata": {"filename": "contract.pdf"}
    }
  ]
}
```

### 3. 자연어 SQL
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "지원자 목록 보여줘"}'
```

**응답**:
```json
{
  "answer": "총 3명의 지원자가 있습니다. ID 1번은 백엔드 개발자...",
  "intent": "sql_query",
  "sql": "SELECT * FROM applicant_info LIMIT 10",
  "results": [
    {"id": 1, "reason": "...", "experience": "...", "skill": "..."},
    ...
  ]
}
```

---

## 아키텍처 다이어그램

```
[Client]
   ↓
[Upload API] ────→ [TextExtractor] ────→ [Qdrant Service] ────→ [Qdrant DB]
   ↓
[Chat API]
   ↓
[QueryRouter] ────→ Intent 분류
   ↓
   ├─→ [RAG Service] ────→ [Qdrant Search] ────→ [Ollama LLM]
   ├─→ [SQL Agent] ────→ [PostgreSQL] ────→ [Ollama LLM]
   └─→ [Ollama Service] ────→ [Ollama LLM]
```

---

## 기존 기능과의 호환성

### 기존 API (변경 없음)
- `POST /api/analysis/summarize/{applicant_id}`
- `POST /api/analysis/keywords/{applicant_id}`
- `POST /api/analysis/interview-questions/{applicant_id}`

### 신규 API (추가됨)
- `POST /api/upload/`
- `GET /api/upload/stats`
- `POST /api/chat/`
- `POST /api/chat/classify`

**결론**: 기존 API는 그대로 동작하며, 신규 API가 추가로 제공됩니다.

---

## 다음 단계 (배포)

1. **패키지 다운로드 (인터넷 환경)**:
```bash
cd backend
pip download -r requirements.txt -d ../python-packages/
```

2. **Qdrant 이미지 내보내기**:
```bash
docker pull qdrant/qdrant:latest
docker save -o qdrant.tar qdrant/qdrant:latest
```

3. **임베딩 모델 다운로드** (옵션):
- Sentence Transformers 모델은 첫 실행 시 자동 다운로드됨
- 폐쇄망 배포 시 미리 다운로드 필요:
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('jhgan/ko-sroberta-multitask')"
# ~/.cache/torch/sentence_transformers/ 에 저장됨
```

4. **서버 배포**:
```bash
# 베이스 이미지 로드
docker load -i qdrant.tar

# Qdrant 실행
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# .env 설정
cd backend
cp .env.example .env
vi .env  # QDRANT_URL 설정

# 빌드 + 실행
cd ..
docker-compose up -d --build
```

---

## 임베딩 모델 및 벡터 DB 커스터마이징

### 기본 설정

**임베딩 모델**: `jhgan/ko-sroberta-multitask`
- 벡터 차원: 768
- 한국어 특화
- 범용 문서 검색에 적합

**벡터 DB**: Qdrant
- Distance: Cosine 유사도
- Collection: `documents` (변경 가능)

### 모델 변경이 필요한 경우

1. **더 빠른 응답 필요**: 384차원 경량 모델로 변경
2. **더 높은 정확도 필요**: 1024차원 대형 모델로 변경
3. **영어 문서 처리**: 영어 특화 모델로 변경
4. **다국어 처리**: 다국어 모델로 변경

### 변경 방법

`.env` 파일에서 모델 이름만 변경:

```bash
# 경량 모델 (빠른 속도)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# 고성능 모델 (높은 정확도)
EMBEDDING_MODEL=intfloat/multilingual-e5-large
```

**중요**: 모델 변경 후에는 반드시:
1. 기존 Qdrant 컬렉션 삭제
2. Backend 재시작
3. 모든 문서 재업로드

**상세 가이드**: [EMBEDDING_MODEL_GUIDE.md](EMBEDDING_MODEL_GUIDE.md) 참조

---

## 문서 업데이트 완료

- ✅ `CLAUDE.md`: RAG 기능 상세 문서화
- ✅ `requirements.txt`: 패키지 추가
- ✅ `.env.example`: 환경 변수 템플릿 업데이트
- ✅ `RAG_IMPLEMENTATION.md`: 구현 완료 보고서 (본 문서)
- ✅ `EMBEDDING_MODEL_GUIDE.md`: 임베딩 모델 및 벡터 DB 변경 가이드 (신규)

---

## 요약

- **구현 완료**: 문서 업로드, RAG 검색, 자연어 SQL, QueryRouter, 채팅 API
- **기존 코드 영향**: 최소화 (backward compatible)
- **캡슐화**: 서비스 레이어로 비즈니스 로직 분리
- **배포 준비**: 폐쇄망 배포 가이드 업데이트 완료
- **다음 작업**: 서버 배포 시 Qdrant 컨테이너 추가, 패키지 다운로드 필요

**참고**: 로컬 테스트를 위해서는 Qdrant, PostgreSQL, Ollama가 모두 실행 중이어야 합니다.
