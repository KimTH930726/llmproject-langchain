# Few-shot Audit 변경 이력 추적 방식 비교 분석

## init.sql 파일 위치
**경로:** `C:\Users\SSG\Downloads\llmproject\init.sql`

- PostgreSQL 컨테이너 초기화 시 자동 실행 (docker-compose.yml 볼륨 마운트)
- 테이블 생성, 인덱스, 샘플 데이터, **트리거** 포함

---

## 구현 방식 비교

### 방식 1: PostgreSQL 트리거 (현재 구현 방식)

#### 코드 구조
**init.sql (트리거 정의)**
```sql
-- 트리거 함수
CREATE OR REPLACE FUNCTION log_few_shot_audit()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO few_shot_audit (few_shot_id, action, old_value, changed_by)
        VALUES (OLD.id, 'DELETE', row_to_json(OLD), 'system');
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO few_shot_audit (few_shot_id, action, old_value, new_value, changed_by)
        VALUES (NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW), 'system');
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO few_shot_audit (few_shot_id, action, new_value, changed_by)
        VALUES (NEW.id, 'INSERT', row_to_json(NEW), 'system');
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 트리거 등록
CREATE TRIGGER few_shot_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON few_shots
    FOR EACH ROW
    EXECUTE FUNCTION log_few_shot_audit();
```

**Python API (backend/app/api/fewshot.py)**
```python
@router.post("/", response_model=FewShotResponse, status_code=201)
async def create_fewshot(fewshot_data: FewShotCreate, session: Session = Depends(get_session)):
    """Few-shot 생성 - Audit 로직 없음, 트리거가 자동 처리"""
    fewshot = FewShot(**fewshot_data.model_dump())
    session.add(fewshot)
    session.commit()  # ← 이 시점에 트리거 자동 실행
    session.refresh(fewshot)
    return fewshot
```

#### 장점
1. **데이터 무결성 보장 (가장 중요)**
   - DB 레벨에서 강제되므로 우회 불가능
   - SQL 직접 실행, ORM 버그, 외부 툴 등 **모든 경로**에서 변경 이력 자동 기록
   - 예: DBeaver에서 직접 `DELETE FROM few_shots WHERE id=1` 실행 → Audit 자동 기록

2. **코드 중복 제거**
   - Python에서 INSERT/UPDATE/DELETE마다 Audit 코드 작성 불필요
   - 유지보수 포인트 단일화 (init.sql만 관리)

3. **성능 최적화**
   - 단일 트랜잭션 내에서 원자적 실행 (네트워크 왕복 없음)
   - Python ↔ DB 왕복 1회로 완료 (Audit 별도 INSERT 불필요)

4. **트랜잭션 일관성**
   - Few-shot 변경과 Audit 기록이 동일 트랜잭션
   - ROLLBACK 시 Audit도 함께 롤백 (데이터 불일치 방지)

5. **에러 처리 자동화**
   - Python에서 예외 발생 시 Audit 누락 위험 없음
   - DB가 책임지므로 애플리케이션 코드 단순화

#### 단점
1. **디버깅 어려움**
   - Python 코드에 Audit 로직이 보이지 않아 초보자는 "어디서 기록되는지" 파악 어려움
   - PostgreSQL 로그 확인 필요

2. **ORM과의 괴리**
   - SQLModel/SQLAlchemy는 Python 객체만 다루므로, 트리거 실행 여부를 코드로 검증 불가
   - 테스트 시 DB 쿼리 직접 확인 필요

3. **배포 복잡도**
   - 폐쇄망 환경: init.sql 누락 시 트리거 미설치 → Audit 이력 0건
   - 마이그레이션 시 트리거 재생성 필수

4. **DB 종속성**
   - PostgreSQL 전용 문법 (MySQL/SQLite 이식 시 재작성 필요)
   - NoSQL 전환 시 트리거 사용 불가

5. **커스터마이징 제약**
   - `changed_by` 필드를 현재 로그인 사용자로 설정하려면 추가 작업 필요
   - 트리거 내에서 애플리케이션 컨텍스트 접근 불가 (현재는 항상 'system')

---

### 방식 2: Python 코드에서 직접 추가 (대안)

#### 코드 구조 (가상 예시)
```python
@router.post("/", response_model=FewShotResponse, status_code=201)
async def create_fewshot(fewshot_data: FewShotCreate, session: Session = Depends(get_session)):
    """Few-shot 생성 + Audit 수동 기록"""
    # 1. Few-shot 생성
    fewshot = FewShot(**fewshot_data.model_dump())
    session.add(fewshot)
    session.flush()  # ID 생성을 위해 flush

    # 2. Audit 수동 기록
    audit = FewShotAudit(
        few_shot_id=fewshot.id,
        action="INSERT",
        new_value=fewshot.model_dump(),
        changed_by="current_user"  # 요청 컨텍스트에서 가져옴
    )
    session.add(audit)

    # 3. 커밋
    session.commit()
    session.refresh(fewshot)
    return fewshot

@router.delete("/{fewshot_id}", status_code=204)
async def delete_fewshot(fewshot_id: int, session: Session = Depends(get_session)):
    """Few-shot 삭제 + Audit 수동 기록"""
    fewshot = session.get(FewShot, fewshot_id)
    if not fewshot:
        raise HTTPException(status_code=404, detail="Not found")

    # 1. Audit 먼저 기록 (삭제 전 데이터 복사)
    audit = FewShotAudit(
        few_shot_id=fewshot.id,
        action="DELETE",
        old_value=fewshot.model_dump(),
        changed_by="current_user"
    )
    session.add(audit)

    # 2. Few-shot 삭제
    session.delete(fewshot)
    session.commit()
    return None
```

#### 장점
1. **명시적 코드 흐름**
   - Audit 기록이 Python 코드에 직접 보임 → 디버깅 쉬움
   - IDE에서 코드 추적 가능 (F12로 정의 이동)

2. **ORM 친화적**
   - SQLModel 객체로 Audit 기록 → 타입 안정성 보장
   - 테스트 시 `session.query(FewShotAudit).count()` 검증 가능

3. **DB 독립성**
   - PostgreSQL/MySQL/SQLite 모두 동일 코드 사용
   - NoSQL로 전환 시에도 로직 재사용 가능

4. **유연한 커스터마이징**
   - `changed_by`를 JWT 토큰에서 추출한 사용자명으로 설정 가능
   - 조건부 Audit (예: 특정 필드 변경 시만 기록) 구현 가능

5. **테스트 용이성**
   - Pytest에서 Audit 객체 생성 검증 가능
   - 모킹/스파이 패턴으로 호출 여부 확인

#### 단점
1. **코드 중복 (가장 심각)**
   - INSERT/UPDATE/DELETE마다 Audit 코드 복사-붙여넣기
   - 유지보수 포인트 3배 증가

2. **데이터 무결성 위험**
   - 개발자가 Audit 코드 누락 시 이력 기록 안 됨
   - SQL 직접 실행 시 우회 가능 (예: `DELETE FROM few_shots WHERE id=1`)

3. **트랜잭션 복잡도 증가**
   - `session.flush()` 타이밍 주의 (ID 생성 전에 Audit 생성 불가)
   - 에러 발생 시 수동 롤백 처리 필요

4. **성능 저하**
   - Python에서 Audit 객체 생성 + DB INSERT 2회 실행
   - 트리거 대비 네트워크 왕복 추가

5. **사이드 이펙트 누락 위험**
   - 예외 발생 시 Audit 기록 전 함수 탈출 가능
   - try-finally 블록으로 보호해야 하지만 코드 복잡도 증가

---

## 의사결정 기준

### PostgreSQL 트리거 선택 (현재 구현, 권장)
**적합한 경우:**
- ✅ 데이터 무결성이 최우선 (감사 로그, 규정 준수)
- ✅ 다양한 경로로 DB 변경 가능 (Admin 툴, 직접 SQL, 배치 작업)
- ✅ PostgreSQL 고정 환경 (폐쇄망 서버)
- ✅ 코드 중복 최소화 필요
- ✅ 성능 최적화 필요 (대량 데이터 변경)

**사용 예:**
- 금융/의료 시스템 (변경 이력 법적 요구사항)
- 멀티 클라이언트 환경 (API, Admin UI, 배치 스크립트)
- 감사 로그가 필수인 엔터프라이즈 애플리케이션

### Python 코드 직접 추가 선택
**적합한 경우:**
- ✅ DB 종속성 회피 필요 (여러 DB 지원 예정)
- ✅ 단일 진입점 보장 (API만 통한 변경, SQL 직접 실행 없음)
- ✅ 복잡한 비즈니스 로직 필요 (조건부 Audit, 외부 API 호출)
- ✅ Python 코드 중심 개발 문화
- ✅ 명시적 코드 선호 (트리거 숨김 로직 거부)

**사용 예:**
- SaaS 프로토타입 (DB 변경 가능성 높음)
- 마이크로서비스 (NoSQL 전환 대비)
- 스타트업 초기 (빠른 코드 이해 우선)

---

## 현재 프로젝트 선택 근거

**PostgreSQL 트리거 방식 채택 이유:**

1. **폐쇄망 환경 특성**
   - PostgreSQL 고정 (DB 변경 가능성 없음)
   - 다양한 관리 경로 예상 (API, DBeaver 등 Admin 툴)

2. **Few-shot 관리의 중요성**
   - Few-shot 변경 이력은 LLM 성능 디버깅의 핵심 데이터
   - 누락 시 "어떤 예제로 학습했는지" 추적 불가 → 치명적

3. **코드 단순성**
   - API 코드에 Audit 로직 없음 → 비즈니스 로직에 집중
   - 신규 개발자 온보딩 시 Few-shot CRUD만 이해하면 됨

4. **성능 요구사항**
   - Few-shot 배치 업데이트 시 트리거가 성능 우위
   - 예: 100개 Few-shot 일괄 비활성화 → Python 200회 INSERT vs 트리거 100회

5. **규정 준수 대비**
   - 향후 내부 감사 시 변경 이력 완전성 보장
   - PostgreSQL 트리거는 "우회 불가능"으로 신뢰도 확보

---

## 트리거 작동 확인 방법

### 1. 폐쇄망 서버에서 트리거 설치 확인
```sql
-- PostgreSQL 접속
docker exec -it postgres psql -U admin -d applicants_db

-- 트리거 존재 확인
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE event_object_table = 'few_shots';

-- 기대 출력:
--   trigger_name          | event_manipulation | event_object_table
-- ------------------------+--------------------+--------------------
--  few_shot_audit_trigger | INSERT             | few_shots
--  few_shot_audit_trigger | UPDATE             | few_shots
--  few_shot_audit_trigger | DELETE             | few_shots
```

### 2. 트리거 함수 코드 확인
```sql
SELECT proname, prosrc
FROM pg_proc
WHERE proname = 'log_few_shot_audit';
```

### 3. 테스트: Few-shot 생성 후 Audit 확인
```sql
-- 1. Few-shot 생성
INSERT INTO few_shots (intent_type, user_query, expected_response, is_active)
VALUES ('rag_search', '테스트 질문', '테스트 답변', true);

-- 2. Audit 테이블 확인
SELECT few_shot_id, action, created_at
FROM few_shot_audit
ORDER BY created_at DESC
LIMIT 5;

-- 기대: INSERT 액션이 기록되어 있어야 함
```

### 4. 트리거 재설치 (이력이 안 쌓일 경우)
```bash
# init.sql의 트리거 부분(147-172줄)만 재실행
docker exec -i postgres psql -U admin -d applicants_db < <(sed -n '147,172p' init.sql)
```

---

## 결론

**현재 프로젝트는 PostgreSQL 트리거 방식이 최적:**
- 데이터 무결성 > 코드 명시성 (Few-shot 이력은 누락 불허)
- 폐쇄망 환경 = PostgreSQL 고정 (DB 독립성 불필요)
- 성능 + 코드 단순성 + 우회 방지 모두 충족

**단, 주의사항:**
- `init.sql` 실행 여부 필수 확인 (배포 체크리스트 포함)
- 트리거 작동 테스트 포함 (CI/CD 파이프라인)
- 문서화 강화 (본 문서를 온보딩 자료에 포함)

---

## 참고 자료

- **트리거 정의:** [init.sql:147-172](init.sql#L147-L172)
- **Few-shot API:** [backend/app/api/fewshot.py](backend/app/api/fewshot.py)
- **Few-shot 모델:** [backend/app/models/few_shot.py](backend/app/models/few_shot.py)
- **Few-shot 기능 가이드:** [FEWSHOT_FEATURE_GUIDE.md](FEWSHOT_FEATURE_GUIDE.md)
