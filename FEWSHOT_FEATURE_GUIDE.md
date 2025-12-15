# Few-shot & Intent 관리 기능 가이드

## 📋 개요

Two-tier Intent 분류와 Few-shot 학습을 활용한 지능형 질의 응답 시스템입니다.

### 주요 기능
1. **Two-tier Intent 분류**
   - **Tier 1**: `intents` 테이블 키워드 매칭 (빠른 응답, LLM 우회)
   - **Tier 2**: LLM 기반 분류 (fallback)
2. **Query Logging** - 모든 사용자 질의 자동 저장
3. **Few-shot 관리** - 질의 로그를 Few-shot 예제로 승격하여 LLM 프롬프트에 활용
4. **Audit 로그** - Few-shot 변경 이력 자동 기록 (INSERT, UPDATE, DELETE)

### 워크플로우
```
사용자 질의 → intents 테이블 확인 → 매칭? (Yes → intent 사용 / No → LLM 분류)
    ↓
Intent별 처리 (RAG/SQL/General) + Few-shot 프롬프트 포함
    ↓
응답 생성 + query_logs 자동 저장
    ↓
Admin 승격 → few_shots 테이블 (is_active=true → 프롬프트에 포함)
```

---

## 🗄️ 데이터베이스 스키마

### 1. `intents` 테이블
키워드 기반 의도 매핑 (Two-tier 분류의 Tier 1)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| keyword | VARCHAR(200) | 키워드 (예: "계약서", "지원자") |
| intent_type | VARCHAR(100) | 의도 타입 (rag_search, sql_query, general) |
| priority | INTEGER | 우선순위 (높을수록 먼저 매칭) |
| description | VARCHAR(500) | 설명 |
| created_at | TIMESTAMP | 생성 시각 |
| updated_at | TIMESTAMP | 수정 시각 |

**동작 원리:**
- 사용자 질의에서 `keyword`가 발견되면 해당 `intent_type` 즉시 반환
- `priority` 순으로 정렬하여 높은 우선순위 키워드 먼저 확인
- 매칭 실패 시 LLM으로 fallback

### 2. `query_logs` 테이블
모든 사용자 질의 자동 저장

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | Primary Key |
| query_text | TEXT | 질의 내용 |
| detected_intent | VARCHAR(100) | 감지된 의도 (rag_search, sql_query, general) |
| response | TEXT | 응답 내용 |
| is_converted_to_fewshot | BOOLEAN | Few-shot으로 승격 여부 |
| created_at | TIMESTAMP | 생성 시각 |

**동작 원리:**
- 모든 채팅 API 호출 시 자동 저장
- Admin이 관리 UI에서 검토 후 Few-shot으로 승격 가능

### 3. `few_shots` 테이블
Few-shot 학습 예제 (LLM 프롬프트에 포함)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| source_query_log_id | BIGINT | FK → query_logs.id (원본 질의 로그) |
| intent_type | VARCHAR(100) | 의도 타입 (rag_search, sql_query, general) |
| user_query | TEXT | 사용자 질의 예제 |
| expected_response | TEXT | 예상 응답 |
| is_active | BOOLEAN | 활성화 여부 (프롬프트 포함 여부) |
| created_at | TIMESTAMP | 생성 시각 |
| updated_at | TIMESTAMP | 수정 시각 (트리거로 자동 업데이트) |

**동작 원리:**
- `is_active=true` few-shots만 LLM 프롬프트에 포함
- Intent별로 필터링 가능 (`intent_type='rag_search'` 등)
- 각 서비스(RAG, SQL Agent, General Chat)가 해당 intent의 few-shots만 조회

### 4. `few_shot_audit` 테이블
Few-shot 변경 이력 (자동 기록)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | Primary Key |
| few_shot_id | INTEGER | FK → few_shots.id |
| action | VARCHAR(20) | INSERT, UPDATE, DELETE |
| old_value | JSONB | 변경 전 값 |
| new_value | JSONB | 변경 후 값 |
| changed_by | VARCHAR(100) | 변경자 (기본값: system) |
| created_at | TIMESTAMP | 생성 시각 |

**트리거:** `few_shots` 테이블의 INSERT/UPDATE/DELETE 시 자동으로 audit 테이블에 기록

---

## 🚀 배포 및 실행

### 1. 데이터베이스 마이그레이션

**방법 1: docker-compose.dev.yml 사용 (권장)**
```bash
# 전체 스택 재시작 (init.sql 자동 실행)
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d

# PostgreSQL 초기화 확인
docker exec postgres psql -U admin -d applicants_db -c "\dt"
```

**방법 2: 기존 DB에 수동 마이그레이션**
```bash
# migrations/ 디렉토리의 SQL 실행
docker exec -i postgres psql -U admin -d applicants_db < migrations/001_create_fewshot_tables.sql

# 또는
psql -U admin -d applicants_db -f migrations/001_create_fewshot_tables.sql
```

### 2. 백엔드 실행

```bash
cd backend

# 의존성 확인 (requirements.txt에 이미 포함됨)
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**또는 Docker:**
```bash
docker-compose -f docker-compose.dev.yml restart backend
```

### 3. 프론트엔드 실행

```bash
cd frontend

# 환경 변수 설정
cp .env.example .env
# .env 파일 확인: VITE_API_BASE_URL=http://localhost:8000

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

**또는 Docker:**
```bash
docker-compose -f docker-compose.dev.yml restart frontend
```

### 4. 접속

- **Frontend**: http://localhost (또는 http://localhost:5173 for Vite dev)
- **Backend API Docs**: http://localhost:8000/docs
- **Intent 관리**: 프론트엔드 첫 번째 탭
- **Few-shot 관리**: 프론트엔드 두 번째 탭

---

## 📡 API 엔드포인트

### Intent API (`/api/intent`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/intent/` | 모든 Intent 목록 조회 |
| GET | `/api/intent/{id}` | 특정 Intent 조회 |
| POST | `/api/intent/` | Intent 생성 |
| PUT | `/api/intent/{id}` | Intent 수정 |
| DELETE | `/api/intent/{id}` | Intent 삭제 |

**생성 예시:**
```bash
curl -X POST http://localhost:8000/api/intent/ \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "계약서",
    "intent_type": "rag_search",
    "priority": 100,
    "description": "계약서 관련 문서 검색"
  }'
```

### Query Log API (`/api/query-logs`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/query-logs/` | 질의 로그 목록 조회 (필터링 가능) |
| POST | `/api/query-logs/` | 질의 로그 생성 (자동 호출용) |
| DELETE | `/api/query-logs/{id}` | 질의 로그 삭제 |
| POST | `/api/query-logs/convert-to-fewshot` | 질의 로그를 Few-shot으로 승격 |
| GET | `/api/query-logs/stats/summary` | 질의 로그 통계 |

**필터링:**
- `?skip=0&limit=100` - 페이지네이션
- `?intent=rag_search` - Intent로 필터링
- `?converted_only=true` - Few-shot 변환된 로그만
- `?search=키워드` - 질의 텍스트 검색

**Few-shot 변환 예시:**
```bash
curl -X POST http://localhost:8000/api/query-logs/convert-to-fewshot \
  -H "Content-Type: application/json" \
  -d '{
    "query_log_id": 1,
    "intent_type": "rag_search",
    "expected_response": "수정된 응답 내용",
    "is_active": true
  }'
```

### Few-shot API (`/api/fewshot`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/fewshot/` | Few-shot 목록 조회 (필터링 가능) |
| GET | `/api/fewshot/{id}` | 특정 Few-shot 조회 |
| POST | `/api/fewshot/` | Few-shot 생성 |
| PUT | `/api/fewshot/{id}` | Few-shot 수정 |
| DELETE | `/api/fewshot/{id}` | Few-shot 삭제 (query_log 플래그 자동 리셋) |

**필터링:**
- `?intent_type=rag_search` - Intent 타입으로 필터링
- `?is_active=true` - 활성화 상태로 필터링

**생성 예시:**
```bash
curl -X POST http://localhost:8000/api/fewshot/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_query_log_id": 1,
    "intent_type": "rag_search",
    "user_query": "계약서 내용이 뭐야?",
    "expected_response": "계약서에는 다음과 같은 내용이 포함되어 있습니다...",
    "is_active": true
  }'
```

### Few-shot Audit API (`/api/fewshot/audit`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/fewshot/audit/` | 모든 Audit 이력 조회 |
| GET | `/api/fewshot/audit/{few_shot_id}` | 특정 Few-shot의 Audit 이력 |

**필터링:**
- `?action=UPDATE` - UPDATE 작업만 조회
- `?limit=100` - 최대 결과 수 제한

**조회 예시:**
```bash
# 특정 Few-shot의 변경 이력
curl http://localhost:8000/api/fewshot/audit/1

# 모든 DELETE 작업 이력
curl http://localhost:8000/api/fewshot/audit/?action=DELETE
```

---

## 🎨 프론트엔드 사용법

### 1. Intent 관리 탭 🎯

키워드 기반 의도 분류를 관리합니다 (Two-tier의 Tier 1).

**기능:**
1. **Intent 추가**
   - "+ 새 Intent" 버튼 클릭
   - 키워드 입력 (예: "계약서", "지원자")
   - Intent 타입 선택 (rag_search / sql_query / general)
   - 우선순위 설정 (높을수록 먼저 매칭)
   - 설명 입력
   - "생성" 버튼 클릭

2. **Intent 수정/삭제**
   - 목록에서 "수정" 또는 "삭제" 버튼 클릭

**동작 방식:**
- 사용자가 "계약서"라는 단어가 포함된 질의를 입력하면
- intents 테이블에서 keyword="계약서"를 찾아 해당 intent_type 즉시 반환
- LLM 호출 없이 빠른 응답 가능

### 2. 질의 로그 관리 탭 💬

모든 사용자 질의가 자동 저장되며, Few-shot으로 승격할 수 있습니다.

**기능:**
1. **질의 로그 검토**
   - 최근 질의 목록 확인
   - 질의 텍스트, 의도, 응답 내용 확인
   - 필터링: Intent별, 변환 여부, 키워드 검색

2. **Few-shot으로 승격**
   - 가치있는 질의를 선택
   - "승격" 버튼 클릭
   - Expected Response 수정 가능
   - Intent 타입 지정
   - 활성화 여부 선택
   - 자동으로 few_shots 테이블에 추가됨

3. **통계 확인**
   - 총 질의 수
   - Few-shot 변환율
   - Intent별 분포

### 3. Few-shot 관리 탭 📚

LLM 프롬프트에 포함될 Few-shot 예제를 관리합니다.

**기능:**
1. **Few-shot 목록**
   - Intent 타입별 필터링 (rag_search / sql_query / general)
   - 활성화 상태 확인 (is_active)
   - 원본 질의 로그 연결 확인 (source_query_log_id)

2. **Few-shot 수정**
   - 사용자 질의 수정
   - 예상 응답 수정
   - 활성화/비활성화 토글

3. **Few-shot 삭제**
   - 삭제 시 연결된 query_log의 is_converted_to_fewshot 플래그 자동 리셋
   - Audit 테이블에 DELETE 이력 자동 기록

4. **변경 이력 조회**
   - Few-shot의 모든 변경 이력 확인
   - INSERT (생성), UPDATE (수정), DELETE (삭제)
   - 변경 전/후 값 비교 (JSONB 형식)

---

## 🧪 테스트 시나리오

### 시나리오 1: Intent 기반 빠른 분류

```bash
# 1. Intent 추가 (키워드 기반)
curl -X POST http://localhost:8000/api/intent/ \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "계약서",
    "intent_type": "rag_search",
    "priority": 100,
    "description": "계약서 관련 문서 검색"
  }'

# 2. 채팅 API로 테스트 ("계약서" 키워드 포함)
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "계약서 내용이 뭐야?"}'

# 결과: intents 테이블에서 매칭되어 즉시 rag_search로 분류됨 (LLM 우회)

# 3. 질의 로그 확인
curl http://localhost:8000/api/query-logs/
```

### 시나리오 2: 질의 로그 → Few-shot 승격

```bash
# 1. 채팅 API 호출 (자동으로 query_logs에 저장됨)
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "지원자 1번의 경력은?"}'

# 2. 질의 로그 조회
curl http://localhost:8000/api/query-logs/?limit=10

# 3. 가치있는 질의를 Few-shot으로 승격 (query_log_id는 2번에서 확인)
curl -X POST http://localhost:8000/api/query-logs/convert-to-fewshot \
  -H "Content-Type: application/json" \
  -d '{
    "query_log_id": 1,
    "intent_type": "sql_query",
    "expected_response": "지원자 1번은 5년간 백엔드 개발 경력을 쌓았습니다.",
    "is_active": true
  }'

# 4. Few-shot 조회 (sql_query intent)
curl http://localhost:8000/api/fewshot/?intent_type=sql_query

# 5. 다음 SQL 질의 시 이 Few-shot이 프롬프트에 포함됨
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "지원자 2번의 기술스택은?"}'
```

### 시나리오 3: Few-shot 활성화/비활성화

```bash
# 1. Few-shot 비활성화 (프롬프트에서 제외)
curl -X PUT http://localhost:8000/api/fewshot/1 \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# 2. Audit 이력 확인 (UPDATE 로그가 자동으로 생성됨)
curl http://localhost:8000/api/fewshot/audit/1

# 3. Few-shot 재활성화
curl -X PUT http://localhost:8000/api/fewshot/1 \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

### 시나리오 4: 통계 확인

```bash
# 질의 로그 통계
curl http://localhost:8000/api/query-logs/stats/summary

# 결과 예시:
# {
#   "total_queries": 150,
#   "converted_count": 12,
#   "conversion_rate": 8.0,
#   "intent_distribution": {
#     "rag_search": 80,
#     "sql_query": 50,
#     "general": 20
#   }
# }
```

---

## 🔧 문제 해결

### 1. 테이블이 생성되지 않았다면

```bash
# 수동으로 마이그레이션 실행
docker exec -i postgres psql -U admin -d applicants_db < migrations/001_create_fewshot_tables.sql

# 테이블 확인
docker exec postgres psql -U admin -d applicants_db -c "\dt"
```

### 2. 프론트엔드에서 API 호출 실패

```bash
# CORS 에러: backend/app/main.py의 allow_origins 확인
# 환경 변수 확인
docker exec backend env | grep VITE_API_BASE_URL

# frontend/.env 파일 확인
cat frontend/.env
```

### 3. Audit 로그가 생성되지 않는다면

```bash
# 트리거 확인
docker exec postgres psql -U admin -d applicants_db -c "\df"

# 트리거 재생성
docker exec -i postgres psql -U admin -d applicants_db < migrations/001_create_fewshot_tables.sql
```

### 4. 백엔드 에러

```bash
# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f backend

# SQLModel 모델 임포트 확인
docker exec backend python -c "from app.models.few_shot import Intent, FewShot"
```

---

## 📊 주요 특징

### 1. Two-tier Intent 분류 (성능 최적화)
- **Tier 1 (키워드 매칭)**: intents 테이블에서 즉시 분류 → LLM 호출 없음 (빠름, 비용 절감)
- **Tier 2 (LLM 분류)**: 매칭 실패 시 fallback → 정확도 보장
- 우선순위(priority) 기반 매칭으로 충돌 방지

### 2. 자동 Query Logging
- 모든 채팅 API 호출 시 자동으로 query_logs 테이블에 저장
- 질의 내용, 의도, 응답 모두 기록
- 데이터 축적을 통한 Few-shot 예제 발굴

### 3. Few-shot Learning (모든 Intent 지원)
- **RAG Search**: 문서 검색 예제 프롬프트에 포함
- **SQL Query**: SQL 생성 및 결과 해석 프롬프트에 포함
- **General Chat**: 일반 대화 프롬프트에 포함
- `is_active=true` few-shots만 프롬프트에 포함 (성능 관리)

### 4. Manual Curation Workflow
- Admin이 query_logs 검토 후 가치있는 질의 선별
- "승격" 버튼으로 Few-shot으로 변환
- 원본 질의와 연결 유지 (source_query_log_id)

### 5. 자동 Audit 로깅
- Few-shot 테이블의 모든 변경사항 자동 기록
- PostgreSQL 트리거 사용 (INSERT/UPDATE/DELETE)
- 변경 전/후 값을 JSONB로 저장

### 6. 양방향 데이터 관리
- Few-shot 삭제 시 query_log의 `is_converted_to_fewshot` 플래그 자동 리셋
- 데이터 일관성 보장

---

## 🎯 실제 사용 시나리오

### 시나리오: 계약서 관련 질의 최적화

1. **초기 상태**: 사용자가 "계약서 내용 알려줘" 질의 → LLM이 intent 분류 (느림)

2. **Intent 추가**: Admin이 keyword="계약서", intent_type="rag_search" 추가
   - 다음부터 "계약서" 키워드 포함 질의는 즉시 rag_search로 분류 (빠름)

3. **질의 축적**: 100개의 계약서 관련 질의가 query_logs에 자동 저장됨

4. **Few-shot 승격**: Admin이 우수 응답 3개를 Few-shot으로 승격
   - 예제 1: "계약서 금액은?" → "계약 금액은 1,000만원입니다."
   - 예제 2: "계약 기간은?" → "계약 기간은 2024년 1월 1일부터..."
   - 예제 3: "계약 당사자는?" → "계약 당사자는 A사와 B사입니다."

5. **효과**: 이후 계약서 질의 시
   - Intent 분류: 키워드 매칭으로 즉시 rag_search (LLM 우회)
   - RAG 답변 생성: 3개 Few-shot 예제가 프롬프트에 포함 → 응답 품질 향상

---

## 🎯 다음 단계

1. ✅ **Two-tier Intent 분류** - 완료
2. ✅ **Query Logging** - 완료
3. ✅ **Few-shot Integration** - 완료 (RAG, SQL, General 모두 지원)
4. 🔄 **프롬프트 최적화**: Few-shot 예제 수 조정, 포맷 개선
5. 🔄 **통계 대시보드**: 의도별 성능 분석, Few-shot 효과 측정
6. 🔄 **자동 Few-shot 추천**: 우수 응답 자동 검출 및 추천

---

## 📝 관련 파일

### Backend - Models
- `backend/app/models/few_shot.py` - Intent, FewShot, FewShotAudit 모델
- `backend/app/models/query_log.py` - QueryLog 모델

### Backend - APIs
- `backend/app/api/chat.py` - 채팅 API (Query Logging 포함)
- `backend/app/api/intent.py` - Intent CRUD API
- `backend/app/api/query_log.py` - Query Log 관리 API (Few-shot 승격 기능)
- `backend/app/api/fewshot.py` - Few-shot CRUD & Audit API

### Backend - Services
- `backend/app/services/query_router.py` - Two-tier Intent 분류
- `backend/app/services/rag_service.py` - RAG + Few-shot
- `backend/app/services/sql_agent.py` - SQL Agent + Few-shot
- `backend/app/services/ollama_service.py` - General Chat + Few-shot

### Database
- `migrations/002_update_fewshot_to_querylog.sql` - QueryLog 워크플로우 마이그레이션
- `init.sql` - 초기화 스크립트 (모든 테이블 + 샘플 데이터)

### Frontend
- `frontend/src/components/IntentManagement.tsx` - Intent 관리 UI
- `frontend/src/components/QueryLogManagement.tsx` - Query Log 관리 UI (승격 기능)
- `frontend/src/components/FewShotManagement.tsx` - Few-shot 관리 UI
- `frontend/src/App.tsx` - 메인 앱 (3 탭 네비게이션)

---

이제 Two-tier Intent 분류와 Few-shot Learning을 완벽하게 활용할 수 있습니다! 🎉

**핵심 워크플로우:**
1. 사용자 질의 → intents 테이블 확인 (빠름)
2. 질의 자동 저장 → query_logs
3. Admin 승격 → few_shots (is_active=true)
4. 다음 질의 시 Few-shot이 프롬프트에 포함 → 응답 품질 향상
