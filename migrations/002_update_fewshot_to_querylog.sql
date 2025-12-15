-- Migration: Few-shot Queries를 Query Logs로 변경
-- 실행 전 백업 필수!

-- 1. 기존 few_shot_queries 테이블 삭제 (데이터 백업 후)
DROP TABLE IF EXISTS few_shot_queries CASCADE;

-- 2. 질의 로그 테이블 생성
CREATE TABLE IF NOT EXISTS query_logs (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    detected_intent VARCHAR(100),
    response TEXT,
    is_converted_to_fewshot BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 질의 로그 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_query_logs_is_converted ON query_logs(is_converted_to_fewshot);
CREATE INDEX IF NOT EXISTS idx_query_logs_intent ON query_logs(detected_intent);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs(created_at DESC);

-- 3. Few-shot 테이블에 source_query_log_id 컬럼 추가
ALTER TABLE few_shots ADD COLUMN IF NOT EXISTS source_query_log_id BIGINT REFERENCES query_logs(id) ON DELETE SET NULL;

-- Few-shot 테이블 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_few_shots_source_query_log_id ON few_shots(source_query_log_id);

-- 완료 메시지
SELECT 'Migration 002 completed successfully' AS status;
