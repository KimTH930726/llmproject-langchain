-- Migration: Create Few-shot and Intent Management Tables
-- Created: 2025-11-05
-- Description: 키워드-의도 매핑, Few-shot 예제 관리, 원문 질의 기록, Audit 테이블 생성

-- 1. Intent 테이블 생성 (키워드-의도 매핑)
CREATE TABLE IF NOT EXISTS intents (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(200) NOT NULL,
    intent_type VARCHAR(100) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    description VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Intent 테이블 인덱스
CREATE INDEX idx_intents_keyword ON intents(keyword);
CREATE INDEX idx_intents_intent_type ON intents(intent_type);
CREATE INDEX idx_intents_priority ON intents(priority DESC);

-- Intent 테이블 코멘트
COMMENT ON TABLE intents IS '키워드와 의도 타입 매핑 테이블';
COMMENT ON COLUMN intents.keyword IS '질의에 포함된 키워드 (예: 검색, 몇명, 안녕)';
COMMENT ON COLUMN intents.intent_type IS '의도 타입 (rag_search, sql_query, general)';
COMMENT ON COLUMN intents.priority IS '우선순위 (높을수록 우선 매칭)';
COMMENT ON COLUMN intents.description IS '키워드에 대한 설명';


-- 2. Few-shot 테이블 생성
CREATE TABLE IF NOT EXISTS few_shots (
    id SERIAL PRIMARY KEY,
    intent_type VARCHAR(100),
    user_query TEXT NOT NULL,
    expected_response TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Few-shot 테이블 인덱스
CREATE INDEX idx_few_shots_intent_type ON few_shots(intent_type);
CREATE INDEX idx_few_shots_is_active ON few_shots(is_active);

-- Few-shot 테이블 코멘트
COMMENT ON TABLE few_shots IS 'Few-shot 예제 관리 테이블';
COMMENT ON COLUMN few_shots.intent_type IS '의도 타입 (rag_search, sql_query, general)';
COMMENT ON COLUMN few_shots.user_query IS '사용자 질의 예제';
COMMENT ON COLUMN few_shots.expected_response IS '예상 응답';
COMMENT ON COLUMN few_shots.is_active IS '활성화 여부';


-- 3. Few-shot 원문 질의 기록 테이블 생성
CREATE TABLE IF NOT EXISTS few_shot_queries (
    id SERIAL PRIMARY KEY,
    few_shot_id INTEGER REFERENCES few_shots(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    detected_intent VARCHAR(100),
    is_converted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Few-shot 원문 질의 테이블 인덱스
CREATE INDEX idx_few_shot_queries_few_shot_id ON few_shot_queries(few_shot_id);
CREATE INDEX idx_few_shot_queries_is_converted ON few_shot_queries(is_converted);
CREATE INDEX idx_few_shot_queries_created_at ON few_shot_queries(created_at DESC);

-- Few-shot 원문 질의 테이블 코멘트
COMMENT ON TABLE few_shot_queries IS '원문 질의 기록 테이블 - Few-shot으로 변환하기 전 원본 쿼리';
COMMENT ON COLUMN few_shot_queries.few_shot_id IS '변환된 Few-shot ID (변환 후)';
COMMENT ON COLUMN few_shot_queries.query_text IS '원문 질의 텍스트';
COMMENT ON COLUMN few_shot_queries.detected_intent IS '감지된 의도';
COMMENT ON COLUMN few_shot_queries.is_converted IS 'Few-shot으로 변환되었는지 여부';


-- 4. Few-shot Audit 테이블 생성
CREATE TABLE IF NOT EXISTS few_shot_audit (
    id SERIAL PRIMARY KEY,
    few_shot_id INTEGER NOT NULL REFERENCES few_shots(id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Few-shot Audit 테이블 인덱스
CREATE INDEX idx_few_shot_audit_few_shot_id ON few_shot_audit(few_shot_id);
CREATE INDEX idx_few_shot_audit_action ON few_shot_audit(action);
CREATE INDEX idx_few_shot_audit_created_at ON few_shot_audit(created_at DESC);

-- Few-shot Audit 테이블 코멘트
COMMENT ON TABLE few_shot_audit IS 'Few-shot 변경 이력 테이블';
COMMENT ON COLUMN few_shot_audit.action IS '변경 작업 (INSERT, UPDATE, DELETE)';
COMMENT ON COLUMN few_shot_audit.old_value IS '변경 전 값 (JSON)';
COMMENT ON COLUMN few_shot_audit.new_value IS '변경 후 값 (JSON)';
COMMENT ON COLUMN few_shot_audit.changed_by IS '변경한 사용자/시스템';


-- 5. 기본 Intent 데이터 삽입 (키워드-의도 매핑 예시)
INSERT INTO intents (keyword, intent_type, priority, description) VALUES
    -- RAG 검색 관련 키워드
    ('검색', 'rag_search', 10, '문서 검색 의도'),
    ('찾아줘', 'rag_search', 10, '문서 찾기 의도'),
    ('알려줘', 'rag_search', 5, '정보 요청 의도'),
    ('문서', 'rag_search', 8, '문서 관련 질의'),

    -- SQL 쿼리 관련 키워드
    ('몇명', 'sql_query', 10, '수량 질의'),
    ('통계', 'sql_query', 10, '통계 질의'),
    ('총', 'sql_query', 8, '집계 질의'),
    ('평균', 'sql_query', 10, '평균 계산 질의'),
    ('개수', 'sql_query', 10, '카운트 질의'),

    -- 일반 대화 키워드
    ('안녕', 'general', 10, '인사 의도'),
    ('고마워', 'general', 10, '감사 표현'),
    ('도와줘', 'general', 5, '도움 요청')
ON CONFLICT DO NOTHING;


-- 6. Trigger: Few-shot updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Few-shot 테이블 트리거
DROP TRIGGER IF EXISTS update_few_shots_updated_at ON few_shots;
CREATE TRIGGER update_few_shots_updated_at
    BEFORE UPDATE ON few_shots
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Intent 테이블 트리거
DROP TRIGGER IF EXISTS update_intents_updated_at ON intents;
CREATE TRIGGER update_intents_updated_at
    BEFORE UPDATE ON intents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- 7. Trigger: Few-shot Audit 자동 기록
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
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS few_shot_audit_trigger ON few_shots;
CREATE TRIGGER few_shot_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON few_shots
    FOR EACH ROW
    EXECUTE FUNCTION log_few_shot_audit();


-- Migration complete
-- 사용법: psql -U admin -d applicants_db -f migrations/001_create_fewshot_tables.sql
