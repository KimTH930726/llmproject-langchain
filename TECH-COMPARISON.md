# 기술 비교 분석

이 문서는 프로젝트에 적용 가능한 기술들의 장단점을 비교 분석합니다.

---

## LangChain vs 현재 구조 (Direct API Calls)

**분석 일자:** 2025-11-06
**현재 상태:** LangChain 미사용, Ollama/Qdrant 직접 호출

### 1. QueryRouter (Intent 분류)

#### 현재 구조
```python
# backend/app/services/query_router.py
- intents 테이블 키워드 매칭 (Two-tier)
- Ollama API 직접 호출 (httpx)
```

#### LangChain 적용 시
```python
from langchain.chains import LLMChain
from langchain_community.llms import Ollama

router = LLMRouterChain(...)
```

| 항목 | 현재 구조 | LangChain |
|------|----------|-----------|
| 코드 간결성 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 커스터마이징 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Two-tier 지원 | ✅ 자연스럽게 구현 | ❌ 복잡해짐 |
| 의존성 | 없음 | langchain-core, langchain-community |

**결론:** 현재 구조 유지 권장 (Two-tier 구조가 효율적)

---

### 2. RAG Service (문서 검색)

#### 현재 구조
```python
# backend/app/services/rag_service.py
- Qdrant 직접 호출
- Sentence Transformers 수동 임베딩
- Ollama API 직접 호출
- Few-shot DB 조회 및 프롬프트 삽입
```

#### LangChain 적용 시
```python
from langchain.vectorstores import Qdrant
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings

vectorstore = Qdrant(...)
qa_chain = RetrievalQA.from_chain_type(
    llm=ollama_llm,
    retriever=vectorstore.as_retriever(),
    chain_type="stuff"
)
```

| 항목 | 현재 구조 | LangChain |
|------|----------|-----------|
| 코드 간결성 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 문서 청킹 | 수동 구현 | ✅ 자동화 |
| Retriever 전략 | 단일 전략 | stuff/map_reduce/refine 선택 가능 |
| Few-shot 통합 | ✅ DB 기반 | 커스터마이징 필요 |
| 의존성 | Qdrant, Sentence Transformers | +langchain-core, langchain-community |
| 패키지 크기 | ~200MB | ~400MB |

**장점:**
- ✅ RAG 파이프라인 표준화 및 코드 30% 감소
- ✅ 다양한 retriever 전략 쉽게 전환
- ✅ 문서 청킹, 메타데이터 관리 자동화

**단점:**
- ❌ Few-shot DB 조회 로직 커스터마이징 필요
- ❌ 폐쇄망 배포 시 패키지 크기 2배 증가
- ❌ 의존성 추가 (~20개 패키지)

**결론:** RAG만 적용한다면 고려 가능, 그러나 폐쇄망 배포 복잡도 증가

---

### 3. SQL Agent (자연어 → SQL)

#### 현재 구조
```python
# backend/app/services/sql_agent.py
- 수동 프롬프트로 SQL 생성
- psycopg2로 직접 실행
- Few-shot SQL 예제 포함
- 결과 해석 프롬프트
```

#### LangChain 적용 시
```python
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_sql_agent

db = SQLDatabase.from_uri(DATABASE_URL)
agent = create_sql_agent(
    llm=ollama_llm,
    toolkit=SQLDatabaseToolkit(db=db, llm=ollama_llm),
    agent_type="zero-shot-react-description"
)
```

| 항목 | 현재 구조 | LangChain |
|------|----------|-----------|
| SQL 생성 | 1회 LLM 호출 | Agent 방식 (여러 번 호출) |
| 오류 수정 | 수동 | ✅ 자동 재시도 |
| 스키마 인식 | 수동 프롬프트 | ✅ 자동 인식 |
| Few-shot 통합 | ✅ DB 기반 | 복잡함 |
| 응답 속도 | 빠름 (~2초) | 느림 (~5-10초) |
| 읽기 전용 제약 | 코드로 제어 | 설정 필요 |

**장점:**
- ✅ SQL 생성, 실행, 오류 수정 자동화
- ✅ 테이블 스키마 자동 인식

**단점:**
- ❌ Agent 방식으로 여러 번 LLM 호출 → 속도 저하
- ❌ Few-shot SQL 예제 통합 복잡
- ❌ 읽기 전용 제약 설정 추가 필요

**결론:** 현재 구조 유지 권장 (속도 우선, Few-shot 통합 용이)

---

### 4. Few-shot 관리

#### 현재 구조
```python
# 각 서비스에서 _get_active_fewshots(session, intent_type) 호출
# PostgreSQL에서 is_active=true 필터링
# 프롬프트에 수동 삽입
```

#### LangChain 적용 시
```python
from langchain.prompts.few_shot import FewShotPromptTemplate
from langchain.prompts.example_selector import SemanticSimilarityExampleSelector

examples = load_fewshots_from_db()
selector = SemanticSimilarityExampleSelector.from_examples(
    examples, embeddings, vectorstore, k=3
)
prompt = FewShotPromptTemplate(
    example_selector=selector, ...
)
```

| 항목 | 현재 구조 | LangChain |
|------|----------|-----------|
| 예제 선택 | is_active 필터링 | ✅ 유사도 기반 선택 |
| 프롬프트 관리 | 수동 삽입 | ✅ 템플릿 표준화 |
| DB 통합 | ✅ PostgreSQL 직접 | 커스터마이징 필요 |
| 동적 개수 조절 | 수동 | ✅ k 파라미터로 자동 |

**장점:**
- ✅ 유사도 기반 Few-shot 자동 선택
- ✅ 프롬프트 템플릿 표준화

**단점:**
- ❌ PostgreSQL → Vector 임베딩 변환 필요
- ❌ is_active 필터링 로직 추가 구현

**결론:** 현재 구조 유지 권장 (PostgreSQL 기반 관리가 더 직관적)

---

## 종합 평가

### LangChain 적용 우선순위

1. **RAG Service** (⭐⭐⭐⭐): 가장 큰 이득, 코드 간소화
2. **Few-shot 관리** (⭐⭐⭐): 유사도 기반 선택은 매력적이나 DB 통합 복잡
3. **SQL Agent** (⭐⭐): 자동화는 좋으나 속도 저하
4. **QueryRouter** (⭐): 현재 구조가 더 효율적

### 폐쇄망 배포 영향

| 항목 | 현재 | LangChain 적용 시 |
|------|------|------------------|
| Python 패키지 수 | 16개 | 30~40개 |
| python-packages 크기 | ~200MB | ~400MB |
| 의존성 충돌 리스크 | 낮음 | 중간 (pydantic 버전) |

### 최종 권장사항

**✅ 현재 구조 유지 (LangChain 미적용)**

**이유:**
1. **폐쇄망 배포 복잡도 증가** - 패키지 크기 2배, 의존성 관리 부담
2. **현재 구조가 이미 효율적** - Two-tier intent, Few-shot DB 통합 잘 작동
3. **응답 속도 우선** - Agent 방식의 여러 번 LLM 호출 불필요
4. **커스터마이징 유연성** - 직접 호출이 프로젝트 요구사항에 더 적합

**대안:**
- 프롬프트 템플릿만 별도 파일로 분리 (`backend/app/prompts/`)
- Few-shot은 현재 PostgreSQL 기반 관리 유지
- RAG는 Qdrant + Sentence Transformers 직접 사용 유지

---

## 추가 기술 비교 (예정)

이 섹션에는 앞으로 분석할 기술들이 추가됩니다:

- [ ] LlamaIndex vs LangChain vs 현재 구조
- [ ] 다른 Vector DB (Chroma, Pinecone, Weaviate) vs Qdrant
- [ ] 다른 LLM (Mistral, Gemma, Qwen) vs llama3.2
- [ ] Alembic (DB 마이그레이션) vs 수동 SQL
- [ ] FastAPI vs Flask vs Django
- [ ] Pydantic v2 vs v1
- [ ] 기타 기술 스택 비교

---

**문서 업데이트 규칙:**
1. 새로운 기술 비교 요청 시 해당 섹션 추가
2. 각 비교는 "현재 구조 vs 대안" 형식 유지
3. 표와 장단점 리스트로 명확하게 정리
4. 폐쇄망 배포 영향 반드시 포함
5. 최종 권장사항 명시
