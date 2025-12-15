# 문서 구조화 전략 가이드

## 개요

벡터 DB(Qdrant)에 문서를 저장할 때, 단순 텍스트 추출만으로는 RAG 성능에 한계가 있습니다.
이 문서는 다양한 문서 구조화 전략을 비교 분석하고, 프로젝트에 적합한 방식을 제안합니다.

## 현재 구조 (Baseline)

### 아키텍처
```
파일 업로드 → 텍스트 추출 → 임베딩 생성 → Qdrant 저장
```

### 현재 코드
```python
# backend/app/api/upload.py
async def upload_document(file: UploadFile = File(...)):
    # 1. 파일에서 텍스트 추출
    file_content = await file.read()
    text = TextExtractor.extract_text(file_content, file.filename)

    # 2. 메타데이터 구성
    metadata = {
        "filename": file.filename,
        "upload_time": datetime.now().isoformat(),
        "file_size": len(file_content),
    }

    # 3. Qdrant에 저장 (전체 텍스트를 하나의 벡터로)
    qdrant_service.add_document(
        doc_id=doc_id,
        text=text,
        metadata=metadata
    )
```

### 장점
- 구현 단순함
- 빠른 업로드 속도
- 저장 공간 효율적

### 단점
- 긴 문서는 벡터 하나로 표현 → 세밀한 검색 불가
- 문서 구조 정보 손실 (제목, 섹션, 단락 구분)
- 메타데이터 부족 → 필터링/분류 어려움
- 문서 타입별 최적화 불가

---

## 전략 1: 문서 타입별 메타데이터 추가

### 개념
파일 형식뿐만 아니라 **문서의 의미적 타입**(이력서, 기술문서, 보고서 등)을 메타데이터로 관리

### 아키텍처
```
파일 업로드
  ↓
사용자 선택: 문서 타입 (이력서 / 기술문서 / 보고서 / 기타)
  ↓
텍스트 추출
  ↓
메타데이터 추가: doc_type, author, category, tags
  ↓
임베딩 생성 → Qdrant 저장
```

### 구현 예시

#### Backend 수정
```python
# backend/app/models/chat.py
class UploadRequest(BaseModel):
    """문서 업로드 요청"""
    file: UploadFile
    doc_type: str  # "resume", "technical_doc", "report", "general"
    author: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

# backend/app/api/upload.py
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    author: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)  # JSON string
):
    text = TextExtractor.extract_text(file_content, file.filename)

    metadata = {
        "filename": file.filename,
        "upload_time": datetime.now().isoformat(),
        "file_size": len(file_content),
        "doc_type": doc_type,
        "author": author,
        "department": department,
        "category": category,
        "tags": json.loads(tags) if tags else []
    }

    qdrant_service.add_document(doc_id, text, metadata)
```

#### Frontend 수정
```typescript
// frontend/src/components/Dashboard.tsx
const [uploadForm, setUploadForm] = useState({
  file: null,
  doc_type: 'general',
  author: '',
  department: '',
  category: '',
  tags: []
});

const handleUpload = async () => {
  const formData = new FormData();
  formData.append('file', uploadForm.file);
  formData.append('doc_type', uploadForm.doc_type);
  formData.append('author', uploadForm.author);
  formData.append('department', uploadForm.department);
  formData.append('category', uploadForm.category);
  formData.append('tags', JSON.stringify(uploadForm.tags));

  await fetch(`${API_BASE_URL}/api/upload/`, {
    method: 'POST',
    body: formData
  });
};
```

#### 검색 시 메타데이터 필터링
```python
# backend/app/services/qdrant_service.py
from qdrant_client.models import Filter, FieldCondition, MatchValue

def search_with_filter(self, query: str, doc_type: str = None, limit: int = 5):
    query_vector = self.embedding_model.encode(query).tolist()

    # 필터 조건 생성
    filter_conditions = None
    if doc_type:
        filter_conditions = Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value=doc_type)
                )
            ]
        )

    search_result = self.client.search(
        collection_name=self.collection_name,
        query_vector=query_vector,
        query_filter=filter_conditions,
        limit=limit
    )

    return search_result
```

### 장점
- 문서 필터링 가능 (예: "기술문서만 검색")
- 문서 출처/작성자 추적
- 카테고리별 통계 집계 가능
- 기존 코드 변경 최소화

### 단점
- 사용자가 메타데이터를 수동 입력해야 함
- 긴 문서 문제 해결 안 됨
- 문서 내부 구조는 여전히 무시

### 적합한 경우
- 문서 개수가 많고 분류 체계가 명확한 경우
- 검색 시 필터링이 자주 필요한 경우
- 메타데이터를 체계적으로 관리할 수 있는 경우

---

## 전략 2: 문서 청킹 (Chunking) 전략

### 개념
긴 문서를 작은 단위(chunk)로 분할하여 저장 → 검색 정확도 향상

### 청킹 방법 비교

#### 2-1. 고정 크기 청킹 (Fixed-size Chunking)
```python
def split_by_fixed_size(text: str, chunk_size: int = 1000, overlap: int = 200):
    """고정 크기로 분할 (오버랩 포함)"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap  # 오버랩
    return chunks
```

**장점:**
- 구현 간단
- 일정한 chunk 크기 → 임베딩 품질 예측 가능

**단점:**
- 문장/단락 중간에서 잘림
- 의미 단위 무시

#### 2-2. 문장 기반 청킹 (Sentence-based Chunking)
```python
import re

def split_by_sentences(text: str, max_sentences: int = 5):
    """문장 단위로 분할"""
    # 한국어 문장 구분 (마침표, 물음표, 느낌표)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    for sentence in sentences:
        current_chunk.append(sentence)
        if len(current_chunk) >= max_sentences:
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks
```

**장점:**
- 의미 단위 유지
- 자연스러운 경계

**단점:**
- chunk 크기 불균형 (문장 길이 차이)
- 한국어 문장 구분 어려움 (마침표 오용)

#### 2-3. 단락 기반 청킹 (Paragraph-based Chunking)
```python
def split_by_paragraphs(text: str):
    """단락 단위로 분할 (빈 줄 기준)"""
    paragraphs = text.split('\n\n')
    return [p.strip() for p in paragraphs if p.strip()]
```

**장점:**
- 주제별 분리
- 문서 구조 반영

**단점:**
- 단락 크기 불균형 심함
- PDF 추출 시 단락 구분 애매함

#### 2-4. 시맨틱 청킹 (Semantic Chunking)
```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def split_by_semantic_similarity(text: str, threshold: float = 0.7):
    """의미적 유사도 기반 분할"""
    model = SentenceTransformer('jhgan/ko-sroberta-multitask')
    sentences = re.split(r'(?<=[.!?])\s+', text)
    embeddings = model.encode(sentences)

    chunks = []
    current_chunk = [sentences[0]]

    for i in range(1, len(sentences)):
        similarity = cosine_similarity(
            [embeddings[i-1]],
            [embeddings[i]]
        )[0][0]

        if similarity < threshold:  # 주제 변경
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentences[i]]
        else:
            current_chunk.append(sentences[i])

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks
```

**장점:**
- 주제별 자동 분리
- 최고 품질

**단점:**
- 계산 비용 높음 (임베딩 2회)
- 구현 복잡

### 권장: 하이브리드 청킹

```python
# backend/app/utils/chunker.py
class DocumentChunker:
    """문서를 의미 단위로 분할하는 유틸리티"""

    @staticmethod
    def chunk_document(
        text: str,
        method: str = "hybrid",
        max_chunk_size: int = 1000,
        min_chunk_size: int = 200,
        overlap: int = 100
    ) -> List[str]:
        """
        하이브리드 청킹 전략
        1. 단락으로 1차 분할
        2. 너무 긴 단락은 문장 단위로 재분할
        3. 너무 짧은 단락은 병합
        """
        # 1단계: 단락 분할
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 2단계: 크기 검사
            if len(para) > max_chunk_size:
                # 너무 긴 단락 → 문장 단위로 분할
                sentences = re.split(r'(?<=[.!?])\s+', para)
                temp_chunk = ""
                for sent in sentences:
                    if len(temp_chunk) + len(sent) > max_chunk_size:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                        temp_chunk = sent
                    else:
                        temp_chunk += " " + sent
                if temp_chunk:
                    chunks.append(temp_chunk.strip())

            elif len(current_chunk) + len(para) < max_chunk_size:
                # 작은 단락 병합
                current_chunk += "\n\n" + para

            else:
                # 현재 chunk 저장 후 새로 시작
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
```

### Qdrant 저장 수정

```python
# backend/app/api/upload.py
from app.utils.chunker import DocumentChunker

async def upload_document(file: UploadFile = File(...)):
    text = TextExtractor.extract_text(file_content, file.filename)

    # 청킹
    chunks = DocumentChunker.chunk_document(text)

    # 각 chunk를 개별 저장
    for idx, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{idx}"
        metadata = {
            "filename": file.filename,
            "upload_time": datetime.now().isoformat(),
            "file_size": len(file_content),
            "parent_doc_id": doc_id,  # 원본 문서 ID
            "chunk_index": idx,
            "total_chunks": len(chunks)
        }

        qdrant_service.add_document(chunk_id, chunk, metadata)

    return {
        "message": "파일 업로드 성공",
        "filename": file.filename,
        "doc_id": doc_id,
        "chunks_created": len(chunks)
    }
```

### 장점
- 검색 정확도 대폭 향상
- 긴 문서도 세밀하게 검색 가능
- RAG 답변 품질 개선

### 단점
- 저장 공간 증가 (chunk 수만큼)
- 임베딩 시간 증가
- 복잡도 증가 (chunk 관리)

### 적합한 경우
- 긴 문서(논문, 매뉴얼, 보고서)가 많은 경우
- 세밀한 검색이 중요한 경우
- 저장 공간보다 검색 품질이 우선인 경우

---

## 전략 3: 구조화된 필드 추출 ⭐ (프로젝트 채택)

### 개념
문서를 **의미적 섹션**으로 분리하여 각 섹션을 개별 필드로 저장

### 문서 타입별 섹션 정의

#### 이력서 (Resume)
```python
RESUME_SECTIONS = {
    "자기소개": ["자기소개", "소개", "지원동기"],
    "경력사항": ["경력", "경력사항", "업무경험", "프로젝트"],
    "기술스택": ["기술", "기술스택", "보유기술", "Skills"],
    "학력": ["학력", "교육"],
    "자격증": ["자격증", "Certificate", "라이센스"]
}
```

#### 기술문서 (Technical Document)
```python
TECH_DOC_SECTIONS = {
    "개요": ["개요", "Overview", "소개", "Introduction"],
    "목적": ["목적", "Purpose", "배경", "Background"],
    "아키텍처": ["아키텍처", "Architecture", "구조", "설계"],
    "기술스택": ["기술스택", "Tech Stack", "기술"],
    "API": ["API", "엔드포인트", "Endpoint"],
    "설치방법": ["설치", "Installation", "Setup"],
    "사용법": ["사용법", "Usage", "예제", "Example"],
    "문제해결": ["문제해결", "Troubleshooting", "FAQ"]
}
```

#### 보고서 (Report)
```python
REPORT_SECTIONS = {
    "요약": ["요약", "Summary", "Executive Summary"],
    "배경": ["배경", "Background", "서론"],
    "분석": ["분석", "Analysis", "결과"],
    "결론": ["결론", "Conclusion", "제안"],
    "참고자료": ["참고", "Reference", "출처"]
}
```

### 구현: 섹션 추출기

```python
# backend/app/utils/section_extractor.py
import re
from typing import Dict, List, Optional

class SectionExtractor:
    """문서에서 구조화된 섹션을 추출"""

    SECTION_PATTERNS = {
        "resume": {
            "자기소개": [r"자기소개", r"소개", r"지원\s*동기"],
            "경력사항": [r"경력", r"경력\s*사항", r"업무\s*경험", r"프로젝트"],
            "기술스택": [r"기술", r"기술\s*스택", r"보유\s*기술", r"Skills?"],
            "학력": [r"학력", r"교육"],
            "자격증": [r"자격증", r"Certificate", r"라이센스"]
        },
        "technical_doc": {
            "개요": [r"개요", r"Overview", r"소개", r"Introduction"],
            "목적": [r"목적", r"Purpose", r"배경", r"Background"],
            "아키텍처": [r"아키텍처", r"Architecture", r"구조", r"설계"],
            "기술스택": [r"기술\s*스택", r"Tech\s*Stack", r"기술"],
            "API": [r"API", r"엔드포인트", r"Endpoint"],
            "설치방법": [r"설치", r"Installation", r"Setup"],
            "사용법": [r"사용법", r"Usage", r"예제", r"Example"],
            "문제해결": [r"문제\s*해결", r"Troubleshooting", r"FAQ"]
        },
        "report": {
            "요약": [r"요약", r"Summary", r"Executive\s*Summary"],
            "배경": [r"배경", r"Background", r"서론"],
            "분석": [r"분석", r"Analysis", r"결과"],
            "결론": [r"결론", r"Conclusion", r"제안"],
            "참고자료": [r"참고", r"Reference", r"출처"]
        }
    }

    @classmethod
    def extract_sections(
        cls,
        text: str,
        doc_type: str = "general"
    ) -> Dict[str, str]:
        """
        문서에서 섹션 추출

        Args:
            text: 전체 문서 텍스트
            doc_type: 문서 타입 (resume, technical_doc, report, general)

        Returns:
            {"섹션명": "섹션 내용"} 딕셔너리
        """
        if doc_type not in cls.SECTION_PATTERNS:
            # 일반 문서는 전체를 content로 반환
            return {"content": text}

        patterns = cls.SECTION_PATTERNS[doc_type]
        sections = {}

        # 각 섹션 헤더 찾기
        section_positions = []
        for section_name, keywords in patterns.items():
            for keyword in keywords:
                # 섹션 헤더 패턴: 줄 시작 + 키워드 + 콜론/줄바꿈
                pattern = rf'^[\s#\*]*({keyword})\s*[:：]?\s*$'
                matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    section_positions.append({
                        "name": section_name,
                        "start": match.end(),
                        "keyword": match.group(1)
                    })
                    break  # 첫 매칭만 사용

        # 위치순 정렬
        section_positions.sort(key=lambda x: x["start"])

        # 섹션 내용 추출
        for i, section in enumerate(section_positions):
            start = section["start"]
            end = section_positions[i + 1]["start"] if i + 1 < len(section_positions) else len(text)
            content = text[start:end].strip()

            # 중복 섹션 처리 (첫 번째만 유지)
            if section["name"] not in sections:
                sections[section["name"]] = content

        # 섹션을 찾지 못한 경우 전체를 content로
        if not sections:
            sections["content"] = text

        return sections

    @classmethod
    def extract_with_fallback(
        cls,
        text: str,
        doc_type: str = "general",
        max_chunk_size: int = 1000
    ) -> Dict[str, str]:
        """
        섹션 추출 시도 → 실패 시 청킹으로 fallback
        """
        sections = cls.extract_sections(text, doc_type)

        # 섹션이 너무 길면 청킹
        result = {}
        for section_name, content in sections.items():
            if len(content) > max_chunk_size:
                # 긴 섹션은 청킹
                from app.utils.chunker import DocumentChunker
                chunks = DocumentChunker.chunk_document(content, max_chunk_size=max_chunk_size)
                for idx, chunk in enumerate(chunks):
                    result[f"{section_name}_part{idx+1}"] = chunk
            else:
                result[section_name] = content

        return result
```

### Qdrant 저장 수정

```python
# backend/app/api/upload.py
from app.utils.section_extractor import SectionExtractor

async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general")
):
    text = TextExtractor.extract_text(file_content, file.filename)

    # 섹션 추출
    sections = SectionExtractor.extract_with_fallback(text, doc_type)

    # 각 섹션을 개별 포인트로 저장
    for section_name, content in sections.items():
        section_id = f"{doc_id}_{section_name}"
        metadata = {
            "filename": file.filename,
            "upload_time": datetime.now().isoformat(),
            "file_size": len(file_content),
            "doc_type": doc_type,
            "parent_doc_id": doc_id,
            "section_name": section_name,
            "total_sections": len(sections)
        }

        qdrant_service.add_document(section_id, content, metadata)

    return {
        "message": "파일 업로드 성공",
        "filename": file.filename,
        "doc_id": doc_id,
        "sections_created": list(sections.keys())
    }
```

### 검색 시 활용

```python
# backend/app/services/rag_service.py
async def search_in_section(
    self,
    query: str,
    doc_type: str = None,
    section_name: str = None,
    limit: int = 5
):
    """특정 섹션에서만 검색"""
    query_vector = self.qdrant.embedding_model.encode(query).tolist()

    filter_conditions = []
    if doc_type:
        filter_conditions.append(
            FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
        )
    if section_name:
        filter_conditions.append(
            FieldCondition(key="section_name", match=MatchValue(value=section_name))
        )

    search_result = self.qdrant.client.search(
        collection_name=self.qdrant.collection_name,
        query_vector=query_vector,
        query_filter=Filter(must=filter_conditions) if filter_conditions else None,
        limit=limit
    )

    return search_result

# 사용 예시
# "Python 경험이 있는 지원자" → resume의 경력사항 섹션에서 검색
results = await rag_service.search_in_section(
    query="Python 경험",
    doc_type="resume",
    section_name="경력사항",
    limit=10
)
```

### 장점
- **의미적 검색**: "경력 중심으로 검색" 같은 섹션별 쿼리 가능
- **구조 보존**: 문서의 의도된 구조 유지
- **해석 용이**: LLM이 섹션명을 보고 맥락 이해
- **메타데이터 풍부**: section_name으로 필터링 가능
- **하이브리드 가능**: 청킹과 결합 가능 (긴 섹션은 자동 분할)

### 단점
- 섹션 헤더 패턴 정의 필요
- PDF/DOCX에서 헤더 추출 실패 가능
- 비정형 문서는 섹션 추출 어려움
- 문서 타입별 패턴 유지보수 필요

### 적합한 경우 ⭐
- **정형화된 문서**가 많은 경우 (이력서, 제안서, 보고서)
- **섹션별 검색**이 중요한 경우
- **구조 정보**가 검색 품질에 영향을 주는 경우
- **현재 프로젝트 (채용 시스템)**: 이력서는 대부분 자기소개/경력/기술스택 섹션 구조

---

## 전략 4: 업로드 전 템플릿 검증

### 개념
사용자가 업로드하기 전에 **필수 섹션 포함 여부**를 검증

### 구현

```python
# backend/app/utils/template_validator.py
class TemplateValidator:
    """문서 템플릿 검증"""

    REQUIRED_SECTIONS = {
        "resume": ["자기소개", "경력사항", "기술스택"],
        "technical_doc": ["개요", "아키텍처", "사용법"],
        "report": ["요약", "분석", "결론"]
    }

    @classmethod
    def validate(cls, text: str, doc_type: str) -> Dict[str, Any]:
        """
        템플릿 검증

        Returns:
            {
                "valid": bool,
                "missing_sections": List[str],
                "found_sections": List[str]
            }
        """
        if doc_type not in cls.REQUIRED_SECTIONS:
            return {"valid": True, "message": "검증 불필요"}

        required = cls.REQUIRED_SECTIONS[doc_type]
        sections = SectionExtractor.extract_sections(text, doc_type)
        found = set(sections.keys())
        missing = [s for s in required if s not in found]

        return {
            "valid": len(missing) == 0,
            "missing_sections": missing,
            "found_sections": list(found),
            "completeness": (len(found) / len(required)) * 100
        }

# backend/app/api/upload.py
@router.post("/validate")
async def validate_document(file: UploadFile = File(...), doc_type: str = Form("general")):
    """업로드 전 문서 검증"""
    file_content = await file.read()
    text = TextExtractor.extract_text(file_content, file.filename)

    validation_result = TemplateValidator.validate(text, doc_type)

    if not validation_result["valid"]:
        return {
            "message": "필수 섹션이 누락되었습니다",
            "validation": validation_result,
            "can_upload": False
        }

    return {
        "message": "검증 통과",
        "validation": validation_result,
        "can_upload": True
    }
```

### Frontend 업로드 플로우

```typescript
// frontend/src/components/Dashboard.tsx
const handleFileSelect = async (file: File, docType: string) => {
  // 1. 검증 요청
  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);

  const validationResponse = await fetch(`${API_BASE_URL}/api/upload/validate`, {
    method: 'POST',
    body: formData
  });

  const validation = await validationResponse.json();

  // 2. 검증 실패 시 경고
  if (!validation.can_upload) {
    alert(`필수 섹션 누락: ${validation.validation.missing_sections.join(', ')}`);
    return;
  }

  // 3. 검증 통과 시 업로드
  await handleUpload(file, docType);
};
```

### 장점
- 데이터 품질 보장
- 불완전한 문서 사전 차단
- 사용자에게 즉각 피드백

### 단점
- 업로드 플로우 복잡화
- 엄격한 검증은 사용자 불편
- 비정형 문서는 검증 불가

### 적합한 경우
- 문서 품질이 매우 중요한 경우
- 사용자가 템플릿을 숙지한 경우
- 내부 업무용 시스템 (통제 가능)

---

## 전략 비교표

| 전략 | 구현 난이도 | 검색 품질 | 저장 효율 | 유지보수 | 사용자 UX | 적합 문서 타입 |
|------|------------|----------|----------|---------|----------|---------------|
| **현재 (Baseline)** | ⭐ 매우 쉬움 | ⭐⭐ 낮음 | ⭐⭐⭐⭐⭐ 최고 | ⭐⭐⭐⭐⭐ 쉬움 | ⭐⭐⭐⭐⭐ 편함 | 짧은 문서 |
| **1. 메타데이터 추가** | ⭐⭐ 쉬움 | ⭐⭐⭐ 보통 | ⭐⭐⭐⭐ 높음 | ⭐⭐⭐⭐ 쉬움 | ⭐⭐⭐ 보통 | 모든 문서 |
| **2. 청킹** | ⭐⭐⭐ 보통 | ⭐⭐⭐⭐⭐ 최고 | ⭐⭐ 낮음 | ⭐⭐⭐ 보통 | ⭐⭐⭐⭐⭐ 편함 | 긴 문서 |
| **3. 구조화 추출** ⭐ | ⭐⭐⭐⭐ 어려움 | ⭐⭐⭐⭐ 높음 | ⭐⭐⭐ 보통 | ⭐⭐ 어려움 | ⭐⭐⭐⭐ 편함 | 정형 문서 |
| **4. 템플릿 검증** | ⭐⭐⭐ 보통 | ⭐⭐⭐⭐ 높음 | ⭐⭐⭐ 보통 | ⭐⭐⭐ 보통 | ⭐⭐ 불편 | 정형 문서 |

---

## 프로젝트 권장 전략: 3번 (구조화된 필드 추출) + 2번 (청킹) 하이브리드

### 이유
1. **현재 프로젝트 도메인**: 채용 시스템 → 이력서는 대부분 섹션 구조 존재
2. **검색 시나리오**: "Python 경험자", "3년 이상 경력자" → 특정 섹션 검색 필요
3. **확장성**: 기술문서, 보고서로 확장 가능
4. **성능**: 섹션별 검색 → 불필요한 섹션 제외 → 정확도 향상

### 구현 로드맵

#### Phase 1: 기본 구조화 추출 (1-2일)
```bash
1. SectionExtractor 구현 (backend/app/utils/section_extractor.py)
2. upload.py 수정 (섹션별 저장)
3. Dashboard.tsx 수정 (섹션 목록 표시)
4. 테스트: 이력서 PDF 업로드 → 섹션별 분리 확인
```

#### Phase 2: 청킹 결합 (1일)
```bash
1. DocumentChunker 구현 (backend/app/utils/chunker.py)
2. extract_with_fallback 추가 (긴 섹션 자동 분할)
3. 테스트: 긴 기술문서 업로드
```

#### Phase 3: 검색 최적화 (1일)
```bash
1. rag_service.py에 search_in_section 추가
2. chat.py에서 의도 분류 → 섹션 필터링 연동
   예: "경력 질문" → section_name="경력사항" 필터
3. 테스트: "Python 경험자 검색" → 경력사항 섹션만 검색
```

#### Phase 4: 메타데이터 강화 (선택, 1일)
```bash
1. 업로드 폼에 doc_type, author, category 필드 추가
2. Dashboard에 필터링 UI 추가
3. 통계: 문서 타입별 개수, 섹션 분포
```

---

## 코드 예시: 최종 구현

### Backend

```python
# backend/app/api/upload.py
from app.utils.section_extractor import SectionExtractor

@router.post("/", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("general")
):
    try:
        # 1. 텍스트 추출
        file_content = await file.read()
        text = TextExtractor.extract_text(file_content, file.filename)

        # 2. 섹션 추출 (긴 섹션은 자동 청킹)
        sections = SectionExtractor.extract_with_fallback(text, doc_type)

        # 3. 문서 ID 생성
        doc_id_raw = f"{file.filename}_{datetime.now().isoformat()}"
        doc_id = hashlib.md5(doc_id_raw.encode()).hexdigest()

        # 4. 각 섹션을 Qdrant에 저장
        for section_name, content in sections.items():
            section_id = f"{doc_id}_{section_name}"
            metadata = {
                "filename": file.filename,
                "upload_time": datetime.now().isoformat(),
                "file_size": len(file_content),
                "doc_type": doc_type,
                "parent_doc_id": doc_id,
                "section_name": section_name,
                "total_sections": len(sections)
            }

            qdrant_service.add_document(section_id, content, metadata)

        return UploadResponse(
            message="파일이 성공적으로 업로드되었습니다",
            filename=file.filename,
            doc_id=doc_id,
            text_length=len(text),
            sections_created=list(sections.keys())
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")
```

### Frontend

```typescript
// frontend/src/components/Dashboard.tsx

// 문서 상세 모달에 섹션 목록 표시
{selectedDoc && selectedDoc.metadata.section_name && (
  <div>
    <label className="block text-sm font-semibold text-purple-900 mb-2">섹션</label>
    <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
      <span className="text-indigo-800 font-medium">
        {selectedDoc.metadata.section_name}
      </span>
      <span className="text-indigo-600 text-sm ml-2">
        ({selectedDoc.metadata.total_sections}개 섹션 중)
      </span>
    </div>
  </div>
)}

// 업로드 폼에 문서 타입 선택 추가
<select
  value={docType}
  onChange={(e) => setDocType(e.target.value)}
  className="px-4 py-2 border border-gray-300 rounded-lg"
>
  <option value="general">일반 문서</option>
  <option value="resume">이력서</option>
  <option value="technical_doc">기술 문서</option>
  <option value="report">보고서</option>
</select>
```

---

## 성능 비교 (예상)

### 테스트 시나리오: "Python 3년 이상 경력자 검색"

| 전략 | 검색 시간 | 관련 문서 재현율 | 정확도 | 저장 공간 (100개 이력서) |
|------|----------|----------------|--------|----------------------|
| Baseline (전체 텍스트) | 50ms | 60% | 65% | 5MB |
| 메타데이터 추가 | 55ms | 65% | 70% | 5.5MB |
| 청킹 (1000자) | 80ms | 85% | 80% | 15MB |
| **구조화 추출** ⭐ | **60ms** | **90%** | **85%** | **8MB** |
| 구조화 + 청킹 | 70ms | 95% | 90% | 12MB |

**결론**: 구조화 추출이 검색 품질과 저장 효율의 최적 균형

---

## 마이그레이션 가이드

### 기존 문서 재처리

```python
# backend/scripts/migrate_documents.py
"""
기존에 저장된 문서를 구조화 형식으로 재처리
"""
import asyncio
from app.services.qdrant_service import qdrant_service
from app.utils.section_extractor import SectionExtractor

async def migrate_existing_documents():
    # 1. 기존 문서 조회
    documents = qdrant_service.get_all_documents(limit=1000)

    for doc in documents:
        # 2. section_name이 없는 문서만 처리
        if "section_name" in doc["metadata"]:
            continue

        print(f"Migrating: {doc['id']}")

        # 3. 섹션 추출
        text = doc["text"]
        doc_type = doc["metadata"].get("doc_type", "general")
        sections = SectionExtractor.extract_with_fallback(text, doc_type)

        # 4. 기존 문서 삭제
        qdrant_service.delete_document(doc["id"])

        # 5. 섹션별로 재저장
        for section_name, content in sections.items():
            new_id = f"{doc['id']}_{section_name}"
            metadata = doc["metadata"].copy()
            metadata.update({
                "section_name": section_name,
                "total_sections": len(sections),
                "migrated": True
            })
            qdrant_service.add_document(new_id, content, metadata)

        print(f"  → {len(sections)} sections created")

if __name__ == "__main__":
    asyncio.run(migrate_existing_documents())
```

실행:
```bash
docker exec backend python scripts/migrate_documents.py
```

---

## 참고 자료

- [Qdrant 필터링 가이드](https://qdrant.tech/documentation/concepts/filtering/)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [Sentence Transformers 한국어 모델](https://huggingface.co/jhgan/ko-sroberta-multitask)

---

## 다음 단계

1. `SectionExtractor` 유틸리티 구현
2. `upload.py` 수정 (섹션별 저장)
3. 이력서 샘플 데이터로 테스트
4. Frontend 섹션 표시 기능 추가
5. 검색 시 섹션 필터링 연동

**구현을 시작하시겠습니까?** 어떤 단계부터 진행할까요?
