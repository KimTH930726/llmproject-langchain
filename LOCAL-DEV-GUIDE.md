# 로컬 개발 환경 가이드

이 가이드는 **로컬 환경에서 전체 스택(PostgreSQL, Ollama, Qdrant 포함)**을 Docker로 실행하는 방법을 설명합니다.

## 🎯 개요

`docker-compose.dev.yml`을 사용하면 다음 서비스가 자동으로 시작됩니다:
- **PostgreSQL** - 지원자 정보 저장 (자동으로 init.sql 실행)
- **Ollama** - LLM 서비스 (llama3.2:1b 모델 다운로드 필요)
- **Qdrant** - 벡터 데이터베이스 (RAG 기능용)
- **Backend** - FastAPI 서버
- **Frontend** - React + Nginx

## 📋 사전 요구사항

- Docker 20.10+
- Docker Compose 2.0+
- 최소 8GB RAM (Ollama 모델 로딩에 필요)

## 🚀 빠른 시작

### 1. 전체 스택 시작

```bash
# 프로젝트 루트 디렉토리에서
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Ollama 모델 다운로드

처음 실행 시 Ollama에 모델을 다운로드해야 합니다:

```bash
# Ollama 컨테이너에 접속하여 모델 다운로드
docker exec -it ollama ollama pull llama3.2:1b

# 모델 다운로드 확인
docker exec -it ollama ollama list
```

### 3. 서비스 상태 확인

```bash
# 모든 컨테이너 상태 확인
docker-compose -f docker-compose.dev.yml ps

# 로그 확인
docker-compose -f docker-compose.dev.yml logs -f

# 특정 서비스 로그만 확인
docker-compose -f docker-compose.dev.yml logs -f backend
```

### 4. 서비스 접속

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (admin/admin123)
- **Ollama**: http://localhost:11434
- **Qdrant Dashboard**: http://localhost:6333/dashboard

## 🧪 테스트

### 1. Health Check

```bash
# Backend 헬스체크
curl http://localhost:8000/health

# Ollama 버전 확인
curl http://localhost:11434/api/version

# Qdrant 헬스체크
curl http://localhost:6333/health
```

### 2. 데이터베이스 확인

```bash
# PostgreSQL 접속
docker exec -it postgres psql -U admin -d applicants_db

# psql 내에서:
# \dt                    -- 테이블 목록
# SELECT * FROM applicant_info;  -- 샘플 데이터 확인
# \q                     -- 종료
```

### 3. 지원자 분석 API 테스트

```bash
# 지원자 요약 (샘플 데이터 ID: 1, 2, 3)
curl -X POST http://localhost:8000/api/analysis/summarize/1

# 키워드 추출
curl -X POST http://localhost:8000/api/analysis/keywords/1

# 면접 예상 질문
curl -X POST http://localhost:8000/api/analysis/interview-questions/1
```

### 4. RAG 기능 테스트

```bash
# 문서 업로드
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@/path/to/document.pdf"

# 업로드된 문서 통계 확인
curl http://localhost:8000/api/upload/stats

# RAG 채팅 (문서 업로드 후)
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "문서 내용에 대해 알려줘"}'
```

## 🔧 개발 워크플로우

### 코드 수정 후 재시작

**Python 코드만 수정한 경우** (requirements.txt 변경 없음):

```bash
# Backend 재시작 (핫 리로드 활성화 시 자동 반영)
docker-compose -f docker-compose.dev.yml restart backend
```

**requirements.txt 수정한 경우**:

```bash
# Backend 재빌드
docker-compose -f docker-compose.dev.yml up -d --build backend
```

**Frontend 코드 수정한 경우**:

```bash
# Frontend 재빌드
docker-compose -f docker-compose.dev.yml up -d --build frontend
```

### 로그 실시간 모니터링

```bash
# 전체 로그
docker-compose -f docker-compose.dev.yml logs -f

# Backend만
docker-compose -f docker-compose.dev.yml logs -f backend

# 특정 컨테이너 여러 개
docker-compose -f docker-compose.dev.yml logs -f backend postgres
```

### 데이터베이스 초기화

```bash
# PostgreSQL 볼륨 삭제 후 재시작 (모든 데이터 삭제됨!)
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d

# init.sql이 자동으로 실행되어 샘플 데이터가 생성됩니다
```

## 🛑 서비스 중지

### 컨테이너만 중지 (데이터 유지)

```bash
docker-compose -f docker-compose.dev.yml down
```

### 컨테이너 + 볼륨 삭제 (모든 데이터 삭제)

```bash
docker-compose -f docker-compose.dev.yml down -v
```

## 🐛 문제 해결

### Backend가 unhealthy 상태인 경우

1. **의존 서비스 확인**:
   ```bash
   # PostgreSQL 상태 확인
   docker exec postgres pg_isready -U admin -d applicants_db

   # Ollama 상태 확인
   docker exec ollama curl http://localhost:11434/api/version

   # Qdrant 상태 확인
   docker exec qdrant curl http://localhost:6333/health
   ```

2. **Backend 로그 확인**:
   ```bash
   docker-compose -f docker-compose.dev.yml logs backend
   ```

3. **환경 변수 확인**:
   ```bash
   docker exec backend env | grep -E "DATABASE_URL|OLLAMA|QDRANT"
   ```

### Ollama 모델이 없는 경우

```bash
# 모델 다운로드
docker exec -it ollama ollama pull llama3.2:1b

# 다운로드된 모델 확인
docker exec ollama ollama list
```

### PostgreSQL 연결 실패

```bash
# PostgreSQL 로그 확인
docker-compose -f docker-compose.dev.yml logs postgres

# 네트워크 연결 확인
docker exec backend ping postgres
```

### Qdrant 연결 실패

```bash
# Qdrant 로그 확인
docker-compose -f docker-compose.dev.yml logs qdrant

# Qdrant 대시보드 접속
open http://localhost:6333/dashboard
```

### 포트 충돌

이미 사용 중인 포트가 있는 경우 `docker-compose.dev.yml`에서 포트를 변경하세요:

```yaml
services:
  postgres:
    ports:
      - "15432:5432"  # 5432 대신 15432 사용
```

## 📊 리소스 사용량 모니터링

```bash
# 컨테이너별 리소스 사용량 확인
docker stats

# 디스크 사용량 확인
docker system df

# 볼륨 사이즈 확인
docker volume ls
docker volume inspect llmproject_ollama_data
```

## 🔄 완전 초기화

모든 것을 처음부터 다시 시작하려면:

```bash
# 1. 모든 컨테이너와 볼륨 삭제
docker-compose -f docker-compose.dev.yml down -v

# 2. 이미지 삭제 (선택사항)
docker rmi llmproject-backend llmproject-frontend

# 3. 다시 시작
docker-compose -f docker-compose.dev.yml up -d --build

# 4. Ollama 모델 다운로드
docker exec -it ollama ollama pull llama3.2:1b
```

## 📝 참고 사항

### docker-compose.yml vs docker-compose.dev.yml

- **docker-compose.yml**: 폐쇄망 배포용 (backend, frontend만 포함)
- **docker-compose.dev.yml**: 로컬 개발용 (모든 서비스 포함)

### 데이터 영속성

다음 볼륨에 데이터가 저장됩니다:
- `llmproject_postgres_data`: PostgreSQL 데이터
- `llmproject_ollama_data`: Ollama 모델 및 설정
- `llmproject_qdrant_data`: Qdrant 벡터 데이터

`docker-compose down` 시 볼륨은 유지되며, `-v` 옵션을 사용해야 삭제됩니다.

### 핫 리로드

Backend는 볼륨 마운트를 통해 코드 변경 시 자동 리로드됩니다:
- `./backend/app:/app/app`

만약 자동 리로드가 작동하지 않으면 `docker-compose restart backend`를 실행하세요.

## 🔗 관련 문서

- [README.md](README.md) - 프로젝트 개요
- [CLAUDE.md](CLAUDE.md) - 개발 가이드
- [SETUP-GUIDE.md](SETUP-GUIDE.md) - 폐쇄망 배포 가이드
