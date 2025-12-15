-- 지원자 테이블 생성 (PostgreSQL 초기화 스크립트)
-- Docker Compose로 PostgreSQL 컨테이너 시작 시 자동 실행됨

CREATE TABLE IF NOT EXISTS applicant_info (
    id BIGSERIAL PRIMARY KEY,
    reason VARCHAR(4000),
    experience VARCHAR(4000),
    skill VARCHAR(4000)
);

-- 샘플 데이터 (테스트용)
-- ID는 자동 증가(BIGSERIAL)되므로 1부터 3까지 순차적으로 생성됨
INSERT INTO applicant_info (reason, experience, skill) VALUES
(
    '저는 귀사의 백엔드 개발자 포지션에 지원하게 되었습니다. 귀사가 최신 기술 스택을 활용하여 혁신적인 서비스를 개발하고 있다는 점에 큰 매력을 느꼈습니다. 특히 대용량 트래픽 처리와 확장 가능한 아키텍처 설계에 중점을 두고 있다는 점이 저의 커리어 목표와 잘 부합합니다. 저는 항상 새로운 기술을 배우고 실무에 적용하는 것을 즐기며, 팀과 협업하여 더 나은 서비스를 만들어가는 과정에 보람을 느낍니다.',
    '대학에서 컴퓨터공학을 전공하며 프로그래밍의 기초를 다졌고, 졸업 후 스타트업에서 Python 기반 웹 서비스 개발을 시작했습니다. 현재까지 5년간 백엔드 개발 경력을 쌓아왔으며, FastAPI와 Django를 활용한 RESTful API 설계 및 구현을 주로 담당해왔습니다. AWS 클라우드 인프라 구축과 Docker를 이용한 컨테이너화 작업도 병행하며 DevOps 역량도 키워왔습니다. Redis를 활용한 캐싱 전략과 PostgreSQL 쿼리 튜닝을 통해 응답 속도를 30% 개선한 경험이 있으며, 최근에는 Langchain과 OpenAI API를 활용한 챗봇 서비스를 개발하여 자연어 처리 기술의 실무 적용 가능성을 확인했습니다.',
    'Python, FastAPI, Django, PostgreSQL, Redis, AWS(EC2, S3, RDS), Docker, Kubernetes, Git, REST API, SQLAlchemy, Langchain, OpenAI API, 데이터베이스 최적화, 클라우드 인프라 설계, 컨테이너화, CI/CD, 코드 리뷰, 페어 프로그래밍'
),
(
    '귀사의 프론트엔드 개발자 포지션에 지원하게 되었습니다. 사용자 경험을 최우선으로 생각하는 귀사의 개발 철학이 저의 가치관과 일치합니다. 디자인과 개발의 경계에서 사용자에게 최고의 경험을 제공하는 것이 저의 목표이며, 귀사와 함께 더 나은 서비스를 만들어가고 싶습니다.',
    '대학 시절 디자인과 개발의 교차점에 매력을 느껴 웹 개발 분야에 입문했고, 3년간 프론트엔드 개발자로 성장해왔습니다. React와 TypeScript를 주력 기술 스택으로 SPA 애플리케이션을 개발해왔으며, 전자상거래 플랫폼의 프론트엔드를 전담하며 Webpack 번들 최적화를 통해 초기 로딩 시간을 40% 단축시켰습니다. React Query를 도입하여 서버 상태 관리를 개선했고, Next.js를 활용한 SSR 구현으로 SEO 성능을 크게 향상시켰습니다. 최근에는 Tailwind CSS와 shadcn/ui를 활용한 디자인 시스템을 구축하고 Storybook으로 컴포넌트 문서화를 체계화했습니다.',
    'React, TypeScript, Next.js, JavaScript, HTML5, CSS3, Tailwind CSS, shadcn/ui, React Query, Webpack, Vite, Storybook, Git, REST API, 웹 접근성(WCAG), SEO 최적화, 반응형 웹, SPA, SSR, 성능 최적화, 디자인 시스템, 컴포넌트 설계'
),
(
    '귀사의 머신러닝 엔지니어 포지션에 지원합니다. 데이터 기반 의사결정과 AI 기술로 비즈니스 가치를 창출하는 귀사의 비전에 깊이 공감합니다. 저는 머신러닝 모델 개발부터 MLOps까지 전 과정에 대한 경험을 보유하고 있으며, 최신 AI 기술을 실무에 적용하는 데 열정을 가지고 있습니다.',
    '통계학을 전공하며 데이터 분석의 기초를 다졌고, 석사 과정에서 딥러닝 연구를 수행하며 컴퓨터 비전과 자연어 처리 분야의 전문성을 쌓았습니다. 현재는 Python을 주 언어로 TensorFlow와 PyTorch를 활용한 머신러닝 모델을 설계하고 학습시키는 업무를 담당하고 있습니다. 추천 시스템 개발 프로젝트에서 협업 필터링과 딥러닝 기법을 결합하여 클릭률을 25% 향상시켰으며, Kubeflow와 MLflow를 활용한 모델 버전 관리 및 배포 파이프라인을 구축했습니다. 대규모 데이터 처리를 위해 Spark와 Airflow를 사용한 데이터 파이프라인을 설계하고 운영해왔으며, 최근에는 LLM Fine-tuning과 RAG 시스템 구축에 관심을 가지고 학습 중입니다.',
    'Python, TensorFlow, PyTorch, scikit-learn, Pandas, NumPy, Hugging Face Transformers, Kubeflow, MLflow, Apache Spark, Apache Airflow, SQL, Git, 딥러닝, 머신러닝, 자연어 처리(NLP), 컴퓨터 비전, 추천 시스템, LLM Fine-tuning, RAG, MLOps, 데이터 파이프라인, A/B 테스트, 모델 최적화'
);

-- 인덱스 생성 (검색 성능 향상)
CREATE INDEX IF NOT EXISTS idx_applicant_info_id ON applicant_info(id);


-- ===================================================
-- Few-shot 및 Intent 관리 테이블 생성
-- ===================================================

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
CREATE INDEX IF NOT EXISTS idx_intents_keyword ON intents(keyword);
CREATE INDEX IF NOT EXISTS idx_intents_intent_type ON intents(intent_type);
CREATE INDEX IF NOT EXISTS idx_intents_priority ON intents(priority DESC);

-- 2. 질의 로그 테이블 생성 (모든 사용자 질의 자동 저장)
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

-- 3. Few-shot 예제 테이블 생성 (승격된 예제만)
CREATE TABLE IF NOT EXISTS few_shots (
    id SERIAL PRIMARY KEY,
    source_query_log_id BIGINT REFERENCES query_logs(id) ON DELETE SET NULL,
    intent_type VARCHAR(100),
    user_query TEXT NOT NULL,
    expected_response TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Few-shot 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_few_shots_source_query_log_id ON few_shots(source_query_log_id);
CREATE INDEX IF NOT EXISTS idx_few_shots_intent_type ON few_shots(intent_type);
CREATE INDEX IF NOT EXISTS idx_few_shots_is_active ON few_shots(is_active);

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
CREATE INDEX IF NOT EXISTS idx_few_shot_audit_few_shot_id ON few_shot_audit(few_shot_id);
CREATE INDEX IF NOT EXISTS idx_few_shot_audit_action ON few_shot_audit(action);
CREATE INDEX IF NOT EXISTS idx_few_shot_audit_created_at ON few_shot_audit(created_at DESC);

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

-- 6. Trigger Function: updated_at 자동 업데이트
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

-- 7. Trigger Function: Few-shot Audit 자동 기록
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

-- Few-shot Audit 트리거
DROP TRIGGER IF EXISTS few_shot_audit_trigger ON few_shots;
CREATE TRIGGER few_shot_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON few_shots
    FOR EACH ROW
    EXECUTE FUNCTION log_few_shot_audit();
