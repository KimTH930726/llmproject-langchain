# 폐쇄망 서버 배포 가이드

## 📋 전제 조건 (폐쇄망 서버에 이미 실행 중)

- Docker & Docker Compose
- PostgreSQL (applicant_info, intents, query_logs, few_shots, few_shot_audit 테이블)
- Ollama (llama3.2:1b 모델)
- Qdrant

**임베딩 모델 개선 (2024-11-09):**
- ❌ 이전: sentence-transformers → 7.97GB
- ✅ 현재: FastEmbed (ONNX Runtime) → 778MB (**90% 감소!**)
- 다국어 모델: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (한국어 포함, 768차원)

---

## 🎯 배포 방식 선택

| 방식 | 파일 크기 | 폐쇄망 작업 | 권장 상황 |
|------|----------|-----------|---------|
| **A. 빌드 이미지 전송** | **~1.05GB** | 이미지 로드만 | 일반적인 경우 (빠름) |
| **B. 베이스+패키지 전송** | **~1.1GB** | 빌드 5-10분 | 디버깅/보안검증 필요 시 |

---

## 🚀 방식 A: 빌드 이미지 전송 (빠름)

### 1단계: 인터넷 환경에서 준비

```bash
cd /path/to/llmproject

# 1. FastEmbed 임베딩 모델 다운로드 (백엔드 빌드 전 필수!)
mkdir -p backend/fastembed_cache
docker run --rm --platform linux/amd64 \
  -v $(pwd)/backend/fastembed_cache:/cache \
  python:3.11-slim \
  bash -c "pip install fastembed==0.3.1 && python -c \"from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', cache_dir='/cache')\""

# 2. Linux AMD64용 Docker 이미지 빌드 (맥/윈도우도 --platform 필수)
docker build --platform linux/amd64 -t llmproject-backend:latest -f backend/Dockerfile backend/
docker build --platform linux/amd64 -t llmproject-frontend:latest -f frontend/Dockerfile frontend/

# 3. 이미지 저장
docker save -o llmproject-backend.tar llmproject-backend:latest    # 767MB
docker save -o llmproject-frontend.tar llmproject-frontend:latest  # 50MB

# 4. 프로젝트 코드 압축 (fastembed_cache 포함!)
cd ..
tar -czf llmproject-code.tar.gz \
  --exclude='llmproject/frontend/node_modules' \
  --exclude='llmproject/backend/__pycache__' \
  --exclude='llmproject/frontend/dist' \
  --exclude='llmproject/*.tar' \
  llmproject/                                                        # ~250MB (fastembed_cache 포함)

# 총 3개 파일 ~1.05GB
```

### 2단계: 폐쇄망 서버로 전송
USB나 내부망으로 3개 파일 복사

### 3단계: 폐쇄망 서버에서 배포

```bash
# 이미지 로드
docker load -i llmproject-backend.tar
docker load -i llmproject-frontend.tar

# 프로젝트 압축 해제
tar -xzf llmproject-code.tar.gz
cd llmproject

# 환경 변수 설정 (기존 서비스 연결 + FastEmbed 캐시 경로)
cat > backend/.env << 'EOF'
DATABASE_URL=postgresql://admin:admin123@postgres-container:5432/applicants_db
OLLAMA_BASE_URL=http://ollama-container:11434
OLLAMA_MODEL=llama3.2:1b
QDRANT_URL=http://qdrant-container:6333
FASTEMBED_CACHE_PATH=/app/fastembed_cache
EOF

# docker-compose.yml 수정 (build → image로 변경)
vi docker-compose.yml
# 각 서비스에서 다음과 같이 수정:
#
# backend:
#   # build:              # ← 이 3줄 주석 처리
#   #   context: .
#   #   dockerfile: backend/Dockerfile.offline
#   image: llmproject-backend:latest  # ← 주석 해제
#   volumes:
#     - ./backend/fastembed_cache:/app/fastembed_cache  # 이미 설정됨
#
# frontend:
#   # build:              # ← 이 3줄 주석 처리
#   #   context: ./frontend
#   #   dockerfile: Dockerfile.offline
#   image: llmproject-frontend:latest  # ← 주석 해제

# 실행
docker-compose up -d

# 확인
docker-compose logs -f backend
curl http://localhost:8000/docs  # Backend API
curl http://localhost/           # Frontend

# 임베딩 모델 로드 확인
docker logs backend 2>&1 | grep -i "fastembed"
# 성공 시 출력:
# ✅ FastEmbed 모델 로드 성공: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
#    캐시 디렉토리: /app/fastembed_cache
```

---

## 🔧 방식 B: 베이스+패키지 전송 (디버깅용, 권장)

### 1단계: 인터넷 환경에서 준비

```bash
cd /path/to/llmproject

# 1. 베이스 이미지 다운로드
docker pull --platform linux/amd64 python:3.11-slim
docker pull --platform linux/amd64 nginx:alpine
docker pull --platform linux/amd64 node:20-alpine
docker save -o python-3.11-slim.tar python:3.11-slim
docker save -o nginx-alpine.tar nginx:alpine
docker save -o node-20-alpine.tar node:20-alpine

# 2. Python 패키지 다운로드
mkdir -p python-packages
docker run --rm --platform linux/amd64 \
  -v $(pwd)/backend:/workspace/backend \
  -v $(pwd)/python-packages:/workspace/python-packages \
  -w /workspace/backend \
  python:3.11-slim \
  pip download -r requirements.txt -d /workspace/python-packages/

# 3. FastEmbed 임베딩 모델 다운로드 (중요!)
mkdir -p backend/fastembed_cache
docker run --rm --platform linux/amd64 \
  -v $(pwd)/backend/fastembed_cache:/cache \
  -v $(pwd)/python-packages:/packages \
  python:3.11-slim \
  bash -c "pip install --no-index --find-links=/packages fastembed && python -c \"from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-mpnet-base-v2', cache_dir='/cache')\""

# 4. 프론트엔드 node_modules 다운로드
docker run --rm --platform linux/amd64 \
  -v $(pwd)/frontend:/workspace \
  -w /workspace \
  node:20-alpine \
  npm install

# 5. 압축 (node_modules, python-packages, fastembed_cache 포함)
cd ..
tar -czf llmproject-full.tar.gz llmproject/  # ~1.1GB
```

### 2단계: 폐쇄망 서버로 전송
USB나 내부망으로 llmproject-full.tar.gz 복사

### 3단계: 폐쇄망 서버에서 배포

```bash
# 압축 해제
tar -xzf llmproject-full.tar.gz
cd llmproject

# 베이스 이미지 로드
docker load -i python-3.11-slim.tar
docker load -i nginx-alpine.tar
docker load -i node-20-alpine.tar

# 환경 변수 설정
cat > backend/.env << 'EOF'
DATABASE_URL=postgresql://admin:admin123@postgres-container:5432/applicants_db
OLLAMA_BASE_URL=http://ollama-container:11434
OLLAMA_MODEL=llama3.2:1b
QDRANT_URL=http://qdrant-container:6333
FASTEMBED_CACHE_PATH=/app/fastembed_cache
EOF

# docker-compose.yml 확인 (방식 B는 build 사용)
# backend: dockerfile: backend/Dockerfile.offline (FastEmbed 캐시 포함)
# frontend: dockerfile: Dockerfile.offline (node_modules 사전 다운로드 활용)

# .dockerignore 임시 백업 (frontend/node_modules 복사 허용)
mv frontend/.dockerignore frontend/.dockerignore.bak

# 빌드 및 실행 (폐쇄망에서 로컬 패키지로 설치)
docker-compose up -d --build

# .dockerignore 복원
mv frontend/.dockerignore.bak frontend/.dockerignore

# 확인
docker-compose logs -f backend
docker logs backend 2>&1 | grep -i "fastembed"
# 성공 시 출력:
# ✅ FastEmbed 모델 로드 성공: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
#    캐시 디렉토리: /app/fastembed_cache
```

---

## 🔗 네트워크 연결 (기존 서비스와 통신)

### 방법 1: docker-compose.yml에서 기존 네트워크 사용

```yaml
# docker-compose.yml 수정
networks:
  app-network:
    external: true  # 기존 네트워크 사용
    name: existing-network-name  # 서버의 기존 네트워크 이름
```

### 방법 2: 컨테이너 시작 후 네트워크 연결

```bash
docker network connect existing-network backend
docker network connect existing-network frontend
```

### 네트워크/컨테이너 확인 방법

```bash
# 실행 중인 컨테이너 확인
docker ps

# 네트워크 목록 확인
docker network ls

# 네트워크 상세 정보 (컨테이너 연결 상태)
docker network inspect <network-name>
```

---

## 🗄️ PostgreSQL 테이블 생성

서버의 PostgreSQL에 필요한 테이블을 생성합니다.

### 1. init.sql 실행 (최초 1회)

```bash
# 방법 1: init.sql 파일 직접 실행 (권장)
docker exec -i postgres-container-name psql -U admin -d applicants_db < init.sql

# 방법 2: PostgreSQL 컨테이너에서 대화형으로 실행
docker exec -it postgres-container-name psql -U admin -d applicants_db
applicants_db=# \i /path/to/init.sql
```

**주요 테이블 (init.sql 참고):**
- `applicant_info`: 지원자 정보 (읽기 전용)
- `intents`: 키워드 → intent_type 매핑
- `query_logs`: 질의 로그 자동 저장
- `few_shots`: Few-shot 예제
- `few_shot_audit`: 변경 이력 (트리거 자동 생성)

### 2. 트리거 설치 확인 (필수!)

**Few-shot Audit 트리거가 설치되었는지 반드시 확인하세요.**

```bash
# PostgreSQL 접속
docker exec -it postgres-container-name psql -U admin -d applicants_db

# 트리거 존재 확인
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE event_object_table = 'few_shots';
```

**기대 출력:**
```
       trigger_name        | event_manipulation | event_object_table
---------------------------+--------------------+--------------------
 few_shot_audit_trigger    | INSERT             | few_shots
 few_shot_audit_trigger    | UPDATE             | few_shots
 few_shot_audit_trigger    | DELETE             | few_shots
(3 rows)
```

**만약 출력이 비어있으면 (트리거 없음):**
```bash
# init.sql의 트리거 부분만 재실행
docker exec -it postgres-container-name psql -U admin -d applicants_db << 'EOF'
-- 트리거 함수 생성
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

-- 트리거 생성
DROP TRIGGER IF EXISTS few_shot_audit_trigger ON few_shots;
CREATE TRIGGER few_shot_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON few_shots
    FOR EACH ROW
    EXECUTE FUNCTION log_few_shot_audit();
EOF
```

### 3. 트리거 작동 테스트 (권장)

```sql
-- 1. 테스트 Few-shot 생성
INSERT INTO few_shots (intent_type, user_query, expected_response, is_active)
VALUES ('test', '테스트 질문', '테스트 답변', true)
RETURNING id;

-- 2. Audit 테이블 확인 (방금 생성한 ID로 확인)
SELECT few_shot_id, action, created_at
FROM few_shot_audit
WHERE few_shot_id = <방금_생성된_ID>
ORDER BY created_at DESC;

-- 3. 테스트 데이터 삭제
DELETE FROM few_shots WHERE intent_type = 'test';

-- 4. 최종 확인: DELETE 액션도 기록되었는지 확인
SELECT few_shot_id, action, created_at
FROM few_shot_audit
WHERE few_shot_id = <방금_생성된_ID>
ORDER BY created_at DESC;
-- INSERT와 DELETE 두 레코드가 보여야 함
```

**⚠️ 중요:** 트리거가 없으면 Few-shot 변경 이력이 절대 기록되지 않습니다!

---

## 🔧 문제 해결

### FastEmbed 모델 로드 실패

**증상:** `HuggingFace Hub 접속 시도` 또는 `KeyboardInterrupt`

**원인:**
1. Dockerfile.offline에서 FastEmbed 캐시를 COPY하지 않음
2. 폐쇄망에서 인터넷 접속 시도

**해결:**
```bash
# 1. 캐시 디렉토리 확인
docker exec backend ls -la /app/fastembed_cache/
docker exec backend find /app/fastembed_cache/ -type f

# 2. 예상 구조 (HuggingFace Hub 캐시 형식)
# /app/fastembed_cache/
# └── models--xenova--paraphrase-multilingual-mpnet-base-v2/
#     ├── blobs/
#     ├── refs/
#     └── snapshots/

# 3. 인터넷 환경에서 FastEmbed 모델 재다운로드 후 재배포
```

### PostgreSQL 연결 실패

**증상:** `could not connect to server`

**해결:**
```bash
# 1. 네트워크 연결 확인
docker exec backend ping postgres-container-name

# 2. PostgreSQL 컨테이너 확인
docker ps | grep postgres

# 3. .env 파일 확인
docker exec backend cat /app/.env

# 4. 연결 테스트
docker exec backend python -c "
from sqlmodel import create_engine
import os
from dotenv import load_dotenv
load_dotenv()
url = os.getenv('DATABASE_URL')
print(f'Connecting to: {url}')
engine = create_engine(url)
print('Connection successful!')
"
```

### Ollama 연결 실패

**증상:** `Connection refused` on port 11434

**해결:**
```bash
# 1. Ollama 컨테이너 확인
docker ps | grep ollama

# 2. 네트워크 연결 확인
docker exec backend curl http://ollama-container-name:11434/api/version

# 3. .env 파일에서 OLLAMA_BASE_URL 확인
docker exec backend cat /app/.env | grep OLLAMA
```

### Qdrant 연결 실패

**증상:** `Connection error` to Qdrant

**해결:**
```bash
# 1. Qdrant 컨테이너 확인
docker ps | grep qdrant

# 2. 네트워크 연결 확인
docker exec backend curl http://qdrant-container:6333/collections

# 3. .env 파일 확인
docker exec backend cat /app/.env | grep QDRANT
```

### .env 파일 수정 후 재시작

```bash
# 환경 변수만 변경한 경우 (빌드 불필요)
docker-compose restart backend

# 소스 코드 변경한 경우 (재빌드 필요)
docker-compose up -d --build backend
```

### 전체 재시작

```bash
# 중지
docker-compose down

# 재빌드 + 실행
docker-compose up -d --build
```

---

## 🔐 보안 고려사항

### 운영 환경 설정

**1. 기본 비밀번호 변경**
```bash
# backend/.env 파일에서
DATABASE_URL=postgresql://admin:강력한비밀번호@postgres:5432/applicants_db
```

**2. 포트 제한 (필요 시)**
```yaml
# docker-compose.yml 수정
services:
  backend:
    ports:
      - "127.0.0.1:8000:8000"  # localhost만 허용
  frontend:
    ports:
      - "0.0.0.0:80:80"  # 모든 IP 허용
```

**3. 네트워크 격리**
- Backend, Frontend, PostgreSQL, Ollama를 같은 Docker 네트워크에 배치
- 외부 노출이 필요한 Frontend만 포트 오픈

---

## 📝 참고사항

### 베이스 이미지 목록

| 이미지 | 용도 | 크기 (약) |
|--------|------|-----------|
| `python:3.11-slim` | Backend 실행 환경 | ~150MB |
| `node:20-alpine` | Frontend 빌드 | ~180MB |
| `nginx:alpine` | Frontend 서빙 | ~40MB |

### Docker 네트워크 연결 방법

**1. 컨테이너 이름으로 연결 (권장)**
```bash
OLLAMA_BASE_URL=http://ollama:11434
DATABASE_URL=postgresql://admin:pass@postgres:5432/db
```

**2. IP 주소로 연결**
```bash
# PostgreSQL 컨테이너 IP 확인
docker inspect postgres-container-name | grep IPAddress

# .env에 IP 입력
DATABASE_URL=postgresql://admin:pass@172.17.0.2:5432/db
```

**3. 호스트 네트워크 사용**
```bash
# docker-compose.yml 수정
services:
  backend:
    network_mode: "host"
```

### 배포 체크리스트

**사전 확인:**
- [ ] PostgreSQL, Ollama, Qdrant 실행 중
- [ ] init.sql로 테이블 생성 완료
- [ ] **Few-shot Audit 트리거 설치 확인 (필수!)** ← 위 섹션 참고
- [ ] 네트워크 이름/컨테이너명 확인
- [ ] FastEmbed 캐시 디렉토리 존재 확인

**배포 후 검증:**
```bash
# API 확인
curl http://localhost:8000/docs
curl http://localhost/

# 로그 확인 (연결 오류 체크)
docker logs backend --tail 50
docker logs frontend --tail 50

# FastEmbed 모델 로드 확인
docker logs backend 2>&1 | grep "FastEmbed"

# 트리거 작동 확인 (중요!)
docker exec -it postgres-container-name psql -U admin -d applicants_db \
  -c "SELECT trigger_name FROM information_schema.triggers WHERE event_object_table = 'few_shots';"
# ↑ 3개 출력되어야 함 (INSERT, UPDATE, DELETE)
```

### FastEmbed 캐시 구조

올바른 캐시 구조 (HuggingFace Hub 형식):
```
backend/fastembed_cache/
└── models--xenova--paraphrase-multilingual-mpnet-base-v2/
    ├── blobs/
    │   └── [모델 파일들]
    ├── refs/
    │   └── main
    └── snapshots/
        └── [snapshot hash]/
            ├── config.json
            ├── model.onnx
            ├── tokenizer.json
            └── ...
```

만약 구조가 다르면 인터넷 환경에서 재다운로드 필요.
