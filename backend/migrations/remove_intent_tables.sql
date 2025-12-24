-- Migration: Intent 테이블 제거
-- Tool-based Agent로 전환하면서 Intent classification이 불필요해짐
-- LLM이 Tool을 직접 선택하므로 intents, few_shots 테이블 제거

-- 1. Few-shot Audit 트리거 제거
DROP TRIGGER IF EXISTS few_shot_audit_trigger ON few_shots;
DROP FUNCTION IF EXISTS log_few_shot_audit();

-- 2. Few-shot Audit 테이블 제거
DROP TABLE IF EXISTS few_shot_audit;

-- 3. Few-shots 테이블 제거
DROP TABLE IF EXISTS few_shots;

-- 4. Intents 테이블 제거
DROP TABLE IF EXISTS intents;

-- 5. QueryLog 테이블에서 불필요한 컬럼 제거 (선택사항)
-- detected_intent, is_converted_to_fewshot 컬럼은 남겨둠 (기존 데이터 호환성)
-- 필요시 나중에 제거 가능:
-- ALTER TABLE query_logs DROP COLUMN IF EXISTS detected_intent;
-- ALTER TABLE query_logs DROP COLUMN IF EXISTS is_converted_to_fewshot;

-- 완료 메시지
SELECT 'Intent tables removed successfully. Tool-based Agent is now active.' AS message;
