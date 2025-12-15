# Multi-Stage RAG 기술 문서

## 개요

Multi-Stage RAG는 사용자 질의를 비정형/정형 데이터로 분해하고, 연관성 분석을 통해 AI 답변의 투명성을 확보하는 3단계 파이프라인입니다.

### 핵심 개념

**정형 데이터의 확장된 정의:**
- 기존: RDB 테이블의 컬럼값만 정형 데이터로 간주
- **확장**: 문서 내 구조화된 필드(금액, 날짜, 이름, 수량 등)도 정형 데이터로 분류
- 장점: RAG 검색만으로 정형/비정형 데이터를 동시에 처리 가능

**예시:**
```
질의: "이 계약의 배경과 금액을 알려줘"

분해 결과:
- 비정형: "계약 체결 배경과 목적" → 문맥 이해 필요
- 정형: "계약 금액" → 문서 내 특정 필드값 추출
- DB 쿼리 필요: false (문서에서 해결 가능)
```

---

## 아키텍처

### 전체 플로우

```
사용자 질의
    ↓
┌─────────────────────────────────────────┐
│ Stage 1: Query Decomposition           │
│ - LLM이 질의를 분석하여 분해            │
│ - 비정형/정형 분류 + 사유 제공          │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 2: Intent Classification         │
│ - Two-Tier 방식으로 intent 분류         │
│ - RAG / SQL / General 선택              │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 3: Enhanced RAG Search            │
│ - 비정형 질의로 Qdrant 검색             │
│ - Few-shot 예제 주입                    │
│ - LLM 답변 생성                         │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Stage 4: Relevance Analysis             │
│ - 검색 결과의 연관성 분석               │
│ - 신뢰도 점수 + 사용된 섹션 반환        │
└─────────────────────────────────────────┘
    ↓
최종 응답 (답변 + 분해 사유 + 연관성 분석)
```

---

## Stage 1: Query Decomposition

### 구현: `query_decomposer.py`

**목적:** 사용자 질의를 비정형/정형 요소로 분해하고 분류 사유 제공

**LLM 프롬프트 구조:**
```python
def _build_decomposition_prompt(self, query: str) -> str:
    return f"""다음 사용자 질의를 분석하여 비정형 데이터와 정형 데이터 질의로 분해하세요.

# 정의
- **비정형 질의**: 문맥, 이유, 배경, 설명 등 문서의 자연어 내용을 이해해야 답변 가능
- **정형 질의**: 금액, 날짜, 이름, 수량 등 문서 내 구조화된 필드값을 추출하면 답변 가능
- **DB 쿼리 필요**: 문서가 아닌 데이터베이스 테이블에서 조회해야 하는 질문 (예: 통계, 집계)

# 사용자 질의
"{query}"

# 응답 형식 (JSON만 출력)
{{
  "unstructured_query": "비정형 질의 내용 (없으면 null)",
  "structured_query": "정형 질의 내용 (없으면 null)",
  "needs_db_query": true 또는 false,
  "decomposition_reasoning": "분류 사유 설명"
}}
"""
```

**응답 예시:**
```json
{
  "unstructured_query": "계약 체결의 배경과 목적",
  "structured_query": "계약 금액 및 계약 기간",
  "needs_db_query": false,
  "decomposition_reasoning": "배경과 목적은 문맥 이해가 필요한 비정형 질의. 금액과 기간은 문서 내 구조화된 필드값 추출로 해결 가능. 통계나 집계가 아니므로 DB 쿼리 불필요."
}
```

**핵심 로직:**
```python
async def decompose_query(self, original_query: str) -> Dict[str, Any]:
    # 1. LLM 호출
    prompt = self._build_decomposition_prompt(original_query)
    response = await self.ollama.generate(prompt)

    # 2. JSON 파싱
    result = self._parse_decomposition_response(response)

    # 3. Fallback (파싱 실패 시)
    if parsing_failed:
        return {
            "unstructured_query": original_query,
            "structured_query": None,
            "needs_db_query": False,
            "decomposition_reasoning": "파싱 실패로 기본 처리"
        }

    return result
```

---

## Stage 2: Enhanced RAG Search

### 구현: `rag_service.py`

**목적:** 분해된 비정형 질의로 검색하고 연관성 분석 수행

**핵심 메서드:**
```python
async def answer_question_with_analysis(
    self,
    original_query: str,      # "계약 배경과 금액 알려줘"
    search_query: str,         # "계약 체결의 배경과 목적" (분해된 비정형 질의)
    top_k: int = 3,
    session: Optional[Session] = None
) -> Dict[str, Any]:
```

**플로우:**
1. **Qdrant 검색**: `search_query` (비정형 질의)로 검색
   - 원본 질의 대신 재구성된 질의 사용 → semantic match 개선
2. **Few-shot 주입**: `_get_active_fewshots(session, "rag_search")`
3. **LLM 답변 생성**: Few-shot + 검색 문서 + 질문 → 프롬프트
4. **연관성 분석**: `_analyze_relevance()` 호출 (Stage 3)

**반환값:**
```python
{
    "answer": "답변 내용",
    "sources": [{"text": "...", "score": 0.85, "metadata": {...}}],
    "has_sources": True,
    "relevance_analysis": {
        "reasoning": "...",
        "confidence": 0.92,
        "matched_sections": [...]
    }
}
```

---

## Stage 3: Relevance Analysis

### 구현: `rag_service._analyze_relevance()`

**목적:** 검색 결과가 왜 적합한지 설명하고 신뢰도 평가

**LLM 프롬프트 구조:**
```python
prompt = f"""다음 질의에 대한 RAG 검색 결과를 분석하여 연관성을 설명하세요.

# 원본 사용자 질의
"{original_query}"

# 검색에 사용된 질의
"{search_query}"

# 검색된 문서 개수
3개

# 검색 점수 (상위 3개)
- 문서 1: 0.857
- 문서 2: 0.742
- 문서 3: 0.691

# 생성된 답변
"{answer}"

# 지시사항
1. 왜 이 검색 결과가 사용자 질의에 대한 답변으로 적합한지 설명
2. 검색 점수와 문서 내용을 바탕으로 신뢰도 평가 (0.0~1.0)
3. 답변에 사용된 주요 문서 섹션 나열

# 응답 형식 (JSON만 출력)
{{
  "reasoning": "연관성 설명 (왜 이 답변이 나왔는지)",
  "confidence": 0.0~1.0 사이 신뢰도 점수,
  "matched_sections": ["사용된 문서 섹션1", "섹션2", ...]
}}
"""
```

**응답 예시:**
```json
{
  "reasoning": "검색된 계약서 1페이지에 '배경 및 목적' 섹션이 명시되어 있고, 3페이지 계약 조건에 금액이 직접 기재되어 있어 높은 신뢰도로 답변 가능",
  "confidence": 0.92,
  "matched_sections": ["1페이지 배경 및 목적", "3페이지 계약 조건"]
}
```

**Fallback (파싱 실패 시):**
```python
avg_score = sum(r["score"] for r in search_results) / len(search_results)
return {
    "reasoning": f"검색된 {len(search_results)}개 문서의 평균 유사도: {avg_score:.2f}",
    "confidence": avg_score,
    "matched_sections": [f"문서 {i+1}" for i in range(min(3, len(search_results)))]
}
```

---

## API 사용법

### 1. 기본 RAG (기존 방식)

**엔드포인트:** `POST /api/chat/`

**요청:**
```json
{
  "query": "계약서에서 금액은?"
}
```

**응답:**
```json
{
  "answer": "계약 금액은 5,000만원입니다.",
  "intent": "rag_search",
  "sources": [
    {
      "text": "계약 금액: 50,000,000원...",
      "score": 0.89,
      "metadata": {"filename": "contract.pdf", "page": 3}
    }
  ]
}
```

**특징:**
- LLM 호출: 1회 (답변 생성)
- 응답 시간: 3-8초
- 사유/연관성 분석 없음

---

### 2. Enhanced RAG (Multi-Stage)

**엔드포인트:** `POST /api/chat/enhanced`

**요청:**
```json
{
  "query": "이 계약이 체결된 배경과 계약 금액을 알려줘"
}
```

**응답:**
```json
{
  "answer": "이 계약은 양사 간 장기 협력 관계 구축을 목적으로 체결되었으며, 계약 금액은 5,000만원입니다.",
  "intent": "rag_search",
  "sources": [
    {
      "text": "본 계약은 양사 간 장기 협력 관계 구축을 목적으로...",
      "score": 0.87,
      "metadata": {"filename": "contract.pdf", "page": 1}
    },
    {
      "text": "계약 금액: 50,000,000원...",
      "score": 0.85,
      "metadata": {"filename": "contract.pdf", "page": 3}
    }
  ],
  "decomposition": {
    "unstructured_query": "계약 체결의 배경과 목적",
    "structured_query": "계약 금액",
    "needs_db_query": false,
    "decomposition_reasoning": "배경은 문맥 이해가 필요한 비정형 질의이고, 금액은 문서 내 구조화된 필드값 추출이므로 정형 질의. 문서 검색만으로 해결 가능하여 DB 쿼리 불필요."
  },
  "relevance_analysis": {
    "reasoning": "검색된 계약서 1페이지에 '배경 및 목적' 섹션이 명시되어 있고, 3페이지 계약 조건에 금액이 직접 기재되어 있어 높은 신뢰도로 답변 가능",
    "confidence": 0.92,
    "matched_sections": ["1페이지 배경 및 목적", "3페이지 계약 조건"]
  }
}
```

**특징:**
- LLM 호출: 3회 (분해 + 답변 + 연관성)
- 응답 시간: 8-15초
- 완전한 투명성 (분해 사유 + 연관성 분석)

---

### 3. 디버깅 엔드포인트

#### 질의 분해만 테스트

**엔드포인트:** `POST /api/chat/decompose`

**요청:**
```json
{
  "query": "최근 3개월 계약 건수와 평균 금액은?"
}
```

**응답:**
```json
{
  "query": "최근 3개월 계약 건수와 평균 금액은?",
  "unstructured_query": null,
  "structured_query": "최근 3개월 계약 건수 및 평균 금액",
  "needs_db_query": true,
  "decomposition_reasoning": "시계열 집계와 통계 계산이 필요하여 데이터베이스 쿼리 필수. 문서 검색으로는 해결 불가능."
}
```

**활용:** QueryDecomposer 프롬프트 튜닝 시 사용

---

## 성능 및 최적화

### 응답 시간 분석 (llama3.2:1b 기준)

| 작업 | 기본 RAG | Enhanced RAG |
|------|----------|--------------|
| Intent 분류 (Tier 1) | < 100ms | < 100ms |
| Query Decomposition | - | 2-3초 |
| Qdrant 검색 | 50-100ms | 50-100ms |
| Few-shot 조회 | < 50ms | < 50ms |
| LLM 답변 생성 | 3-5초 | 3-5초 |
| Relevance Analysis | - | 3-5초 |
| **총 응답 시간** | **3-8초** | **8-15초** |

### 최적화 전략

#### 1. 연관성 분석 병렬 처리 (구현 가능)

**현재 (직렬):**
```python
answer = await self.ollama.generate(prompt)  # 3-5초
relevance = await self._analyze_relevance(...)  # 3-5초
# 총: 6-10초
```

**최적화 (병렬):**
```python
import asyncio

answer_task = asyncio.create_task(self.ollama.generate(prompt))
# 답변을 즉시 반환하고, 연관성 분석은 백그라운드 실행
answer = await answer_task

# 연관성 분석을 별도 API로 분리하거나 WebSocket으로 스트리밍
# GET /api/chat/{query_log_id}/relevance (나중에 조회)
```

**효과:** Enhanced RAG 응답 시간 8-15초 → 5-10초

#### 2. QueryDecomposer Few-shot 학습

현재 QueryDecomposer는 Few-shot 예제 없이 동작합니다. 성능 향상을 위해:

1. **Query Logs에서 분해 패턴 수집**
   - 잘 분해된 질의를 Few-shot으로 승격
   - `intent_type="query_decomposition"` 추가

2. **프롬프트 개선**
   ```python
   # backend/app/services/query_decomposer.py
   def _get_active_fewshots(self, session):
       # Few-shot Integration Pattern 적용
       return session.exec(
           select(FewShot)
           .where(FewShot.is_active == True)
           .where(FewShot.intent_type == "query_decomposition")
       ).all()
   ```

**효과:** 분해 정확도 향상, LLM 호출 시간 약간 증가 (2-3초 → 2.5-3.5초)

#### 3. 캐싱 전략

**질의 분해 결과 캐싱:**
```python
# 유사 질의에 대해 분해 결과 재사용
from functools import lru_cache
import hashlib

def get_query_hash(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()

# Redis 또는 메모리 캐시 사용
cache = {}

async def decompose_query_cached(query: str):
    query_hash = get_query_hash(query)
    if query_hash in cache:
        return cache[query_hash]

    result = await decompose_query(query)
    cache[query_hash] = result
    return result
```

**효과:** 동일/유사 질의 반복 시 2-3초 절약

---

## 하이브리드 검색 (RAG + SQL)

### 시나리오: DB 쿼리와 문서 검색 동시 필요

**질의 예시:**
```
"최근 3개월 계약 건수와 가장 큰 계약의 배경을 알려줘"
```

**분해 결과:**
```json
{
  "unstructured_query": "가장 큰 계약의 체결 배경",
  "structured_query": "최근 3개월 계약 건수",
  "needs_db_query": true,
  "decomposition_reasoning": "계약 건수는 DB 집계 필요, 배경은 문서에서 검색 필요"
}
```

**처리 방식 (chat.py 수정 필요):**
```python
if decomposition_result.get("needs_db_query"):
    # 1. SQL 쿼리 실행
    sql_result = await sql_agent.execute_query(
        decomposition_result["structured_query"],
        session=session
    )

    # 2. RAG 검색 실행 (비정형 질의)
    rag_result = await rag_service.answer_question_with_analysis(
        original_query=query,
        search_query=decomposition_result["unstructured_query"],
        session=session
    )

    # 3. 결과 병합
    combined_answer = f"{sql_result['answer']}\n\n{rag_result['answer']}"

    return ChatResponse(
        answer=combined_answer,
        intent="hybrid",  # 새 intent 추가 필요
        sql=sql_result["sql"],
        results=sql_result["results"],
        sources=rag_result["sources"],
        decomposition=QueryDecomposition(**decomposition_result),
        relevance_analysis=rag_result["relevance_analysis"]
    )
```

---

## 데이터 모델

### QueryDecomposition (Pydantic)

**파일:** `backend/app/models/chat.py`

```python
class QueryDecomposition(BaseModel):
    """질의 분해 결과"""
    unstructured_query: Optional[str] = None
    structured_query: Optional[str] = None
    needs_db_query: bool = False
    decomposition_reasoning: str = ""
```

**필드 설명:**
- `unstructured_query`: 문맥 기반 검색용 질의 (비정형)
- `structured_query`: 필드값 추출용 질의 (정형)
- `needs_db_query`: 데이터베이스 쿼리 필요 여부
- `decomposition_reasoning`: 분류 사유

### RelevanceAnalysis (Pydantic)

```python
class RelevanceAnalysis(BaseModel):
    """연관성 분석 결과"""
    reasoning: str
    confidence: float
    matched_sections: List[str] = []
```

**필드 설명:**
- `reasoning`: 왜 이 답변이 나왔는지 설명
- `confidence`: 신뢰도 점수 (0.0~1.0)
- `matched_sections`: 답변에 사용된 문서 섹션 목록

---

## 제한사항 및 주의사항

### 1. LLM 품질 의존성

**문제:**
- QueryDecomposer와 Relevance Analysis는 LLM의 분석 능력에 의존
- llama3.2:1b 같은 작은 모델은 복잡한 질의 분해에 실패할 수 있음

**완화 방법:**
- Few-shot 예제 추가 (query_decomposition intent)
- 더 큰 모델 사용 (llama3.2:3b, llama3:8b)
- 파싱 실패 시 Fallback 로직 (현재 구현됨)

### 2. JSON 파싱 실패

**문제:**
- LLM이 JSON 형식을 정확히 따르지 않을 수 있음
- 코드 블록 (```) 포함, 추가 설명 포함 등

**완화 방법 (현재 구현됨):**
```python
# 코드 블록 제거
if response.startswith("```"):
    lines = response.split("\n")
    response = "\n".join(lines[1:-1])
    if response.startswith("json"):
        response = response[4:].strip()

# 파싱 실패 시 기본값 반환
try:
    parsed = json.loads(response)
except:
    return default_values
```

### 3. 응답 시간 증가

**트레이드오프:**
- 기본 RAG: 3-8초, 간단한 응답
- Enhanced RAG: 8-15초, 상세한 분석

**권장 사용 패턴:**
- 일반 사용자 질의: `/api/chat/` (빠른 응답)
- 중요 의사결정, 감사 필요 질의: `/api/chat/enhanced` (투명성 우선)

### 4. 정형/비정형 분류의 모호함

**문제:**
- "계약 금액"은 정형이지만, "적정한 계약 금액"은 비정형 (판단 필요)
- LLM이 일관성 없이 분류할 수 있음

**완화 방법:**
- 프롬프트에 명확한 정의 제공 (현재 구현됨)
- Few-shot 예제로 엣지 케이스 학습

---

## 테스트 시나리오

### 시나리오 1: 비정형 단독 질의

**질의:** "이 계약의 목적은 무엇인가?"

**예상 분해:**
```json
{
  "unstructured_query": "계약 체결의 목적",
  "structured_query": null,
  "needs_db_query": false,
  "decomposition_reasoning": "목적은 문맥 이해가 필요한 비정형 질의"
}
```

**처리:** RAG 검색만 수행

---

### 시나리오 2: 정형 단독 질의

**질의:** "계약 금액은?"

**예상 분해:**
```json
{
  "unstructured_query": null,
  "structured_query": "계약 금액",
  "needs_db_query": false,
  "decomposition_reasoning": "금액은 문서 내 구조화된 필드값 추출로 해결 가능"
}
```

**처리:** RAG 검색 (정형 질의로 검색)

---

### 시나리오 3: 비정형 + 정형 혼합

**질의:** "계약 배경과 금액 알려줘"

**예상 분해:**
```json
{
  "unstructured_query": "계약 체결 배경",
  "structured_query": "계약 금액",
  "needs_db_query": false,
  "decomposition_reasoning": "배경은 비정형, 금액은 정형. 둘 다 문서에서 해결 가능"
}
```

**처리:** RAG 검색 (비정형 질의 우선 사용)

---

### 시나리오 4: DB 쿼리 필요

**질의:** "최근 3개월 계약 건수는?"

**예상 분해:**
```json
{
  "unstructured_query": null,
  "structured_query": "최근 3개월 계약 건수",
  "needs_db_query": true,
  "decomposition_reasoning": "시계열 집계가 필요하여 DB 쿼리 필수"
}
```

**처리:** SQL Agent 실행

---

### 시나리오 5: 하이브리드 (구현 필요)

**질의:** "최근 3개월 계약 건수와 가장 큰 계약의 배경"

**예상 분해:**
```json
{
  "unstructured_query": "가장 큰 계약의 배경",
  "structured_query": "최근 3개월 계약 건수",
  "needs_db_query": true,
  "decomposition_reasoning": "건수는 DB 집계, 배경은 문서 검색 필요"
}
```

**처리:** SQL + RAG 병합 (chat.py 수정 필요)

---

## 향후 개선 방향

### 1. Query Decomposer Few-shot 학습
- `intent_type="query_decomposition"` 추가
- 잘 분해된 질의를 Few-shot으로 승격

### 2. 연관성 분석 병렬 처리
- 답변 생성과 연관성 분석 비동기 실행
- WebSocket 스트리밍 응답

### 3. 하이브리드 검색 완전 지원
- RAG + SQL 결과 병합 로직
- `intent="hybrid"` 추가

### 4. 신뢰도 기반 자동 재검색
- `confidence < 0.5` → 자동으로 다른 검색 방법 시도
- 예: RAG 실패 → SQL 시도, 또는 그 반대

### 5. 사용자 피드백 루프
- 연관성 분석 결과에 대한 사용자 평가 (좋아요/싫어요)
- 낮은 평가 → Few-shot 제거, 높은 평가 → Few-shot 추가

---

## 참고 자료

- [CLAUDE.md](CLAUDE.md) - 전체 프로젝트 아키텍처
- [FEWSHOT_FEATURE_GUIDE.md](FEWSHOT_FEATURE_GUIDE.md) - Few-shot 학습 가이드
- [backend/app/services/query_decomposer.py](backend/app/services/query_decomposer.py) - 질의 분해 구현
- [backend/app/services/rag_service.py](backend/app/services/rag_service.py) - RAG + 연관성 분석 구현
- [backend/app/api/chat.py](backend/app/api/chat.py) - Multi-Stage RAG API 엔드포인트
