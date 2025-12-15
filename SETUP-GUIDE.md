# 폐쇄망 서버 배포 가이드

## 📍 전체 흐름

```
[인터넷 환경] → 파일 준비 → USB/파일 전송 → [폐쇄망 서버] → 배포
```

---

## 1️⃣ 인터넷 환경에서 할 일 (사전 준비)

### 준비물 체크리스트
- [ ] Docker 설치
- [ ] Python 3.10+ 설치
- [ ] 이 프로젝트 소스코드

### 실행 순서

#### A. 베이스 Docker 이미지 내보내기

```bash
# 중요: 서버가 amd64 아키텍처인 경우 --platform 옵션 필수

# 1. Python 베이스 이미지 (Backend용)
docker pull --platform linux/amd64 python:3.11-slim
docker save -o python-3.11-slim.tar python:3.11-slim

# 2. Node.js 베이스 이미지 (Frontend 빌드용)
docker pull --platform linux/amd64 node:20-alpine
docker save -o node-20-alpine.tar node:20-alpine

# 3. Nginx 베이스 이미지 (Frontend 서빙용)
docker pull --platform linux/amd64 nginx:alpine
docker save -o nginx-alpine.tar nginx:alpine
```

#### B. Python 패키지 다운로드 (오프라인 설치용)

```bash
# 프로젝트 루트 디렉토리에서 실행
# Docker 사용하여 Linux 환경에서 패키지 다운로드 (권장)

# python-packages 디렉토리 생성
mkdir -p python-packages

# Docker로 Linux 환경에서 다운로드
docker run --rm \
  -v $(pwd)/backend:/workspace/backend \
  -v $(pwd)/python-packages:/workspace/python-packages \
  -w /workspace/backend \
  python:3.11-slim \
  pip download -r requirements.txt -d /workspace/python-packages/
```

**결과:** `python-packages/` 디렉토리에 Linux용 `.whl` 파일들 생성됨

**설명:**
- 프로젝트 루트에서 실행
- `backend/` 와 `python-packages/` 두 디렉토리 모두 마운트
- 컨테이너 내부의 `/workspace/python-packages/`에 저장 → 호스트의 `python-packages/`에 저장됨

#### C. 서버로 전송할 파일 정리

```bash
# 프로젝트 루트 디렉토리 구조 확인
llmproject/
├── backend/                    # 백엔드 소스코드
│   ├── app/
│   ├── Dockerfile.offline
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # 프론트엔드 소스코드
│   ├── src/
│   ├── Dockerfile
│   ├── package.json
│   └── nginx.conf
├── python-packages/            # ✅ 다운받은 Python 패키지들
│   ├── fastapi-xxx.whl
│   ├── sqlmodel-xxx.whl
│   └── ...
├── docker-compose.yml
├── init.sql
├── python-3.11-slim.tar        # ✅ 베이스 이미지
├── node-20-alpine.tar          # ✅ 베이스 이미지
├── nginx-alpine.tar            # ✅ 베이스 이미지
└── SETUP-GUIDE.md              # 이 파일
```

#### D. 파일 전송

위 디렉토리 전체를 압축하여 폐쇄망 서버로 전송:

```bash
# 프로젝트 루트에서
cd ..
tar -czf llmproject.tar.gz llmproject/

# llmproject.tar.gz를 USB 또는 파일 전송 시스템으로 서버에 복사
```

---

## 2️⃣ 폐쇄망 서버에서 할 일 (배포)

### 준비물 체크리스트
- [ ] Docker 설치됨
- [ ] PostgreSQL Docker 컨테이너 실행 중
- [ ] Ollama Docker 컨테이너 실행 중
- [ ] `llmproject.tar.gz` 파일 전송 완료

### 실행 순서

#### A. 파일 압축 해제

```bash
tar -xzf llmproject.tar.gz
cd llmproject
```

#### B. 베이스 이미지 로드

```bash
# Docker에 베이스 이미지 로드
docker load -i python-3.11-slim.tar
docker load -i node-20-alpine.tar
docker load -i nginx-alpine.tar

# 로드 확인
docker images | grep -E "python|node|nginx"
```

**출력 예시:**
```
python       3.11-slim   xxx   xxx   150MB
node         20-alpine   xxx   xxx   180MB
nginx        alpine      xxx   xxx   40MB
```

#### C. 서버의 기존 컨테이너 정보 확인

```bash
# 실행 중인 컨테이너 확인
docker ps

# PostgreSQL 컨테이너 이름 확인 (예: postgres)
# Ollama 컨테이너 이름 확인 (예: ollama)

# Docker 네트워크 확인
docker network ls
# 컨테이너들이 연결된 네트워크 이름 확인 (예: app-network)
```

#### D. 환경 변수 설정

```bash
cd backend
cp .env.example .env
vi .env
```

**수정할 내용:**

```bash
# Ollama 설정 - 서버의 Ollama 컨테이너 주소
OLLAMA_BASE_URL=http://<ollama-container-name>:11434
OLLAMA_MODEL=llama3.2:1b

# PostgreSQL 설정 - 서버의 PostgreSQL 컨테이너 주소
DATABASE_URL=postgresql://<user>:<password>@<postgres-container-name>:5432/<database>
```

**예시:**
```bash
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
DATABASE_URL=postgresql://admin:admin123@postgres:5432/applicants_db
```

**네트워크 연결 방법:**
- **같은 네트워크**: `http://ollama:11434`, `postgres:5432`
- **다른 네트워크**: IP 주소로 연결 (아래 참고)

#### E. Docker 네트워크 연결 (필요 시)

Backend/Frontend를 서버의 기존 PostgreSQL, Ollama와 같은 네트워크에 연결:

**방법 1: docker-compose.yml 수정 (기존 네트워크 사용)**
```bash
vi docker-compose.yml
```

```yaml
networks:
  app-network:
    external: true
    name: <기존-네트워크-이름>  # 예: app-network
```

**방법 2: 빌드 후 수동 연결**
```bash
# Backend, Frontend 실행 후
docker network connect <기존-네트워크-이름> backend
docker network connect <기존-네트워크-이름> frontend
```

#### F. 빌드 및 실행

```bash
cd ..  # 프로젝트 루트로 이동
docker-compose up -d --build
```

**빌드 과정:**
1. Backend: `python-packages/`에서 오프라인 설치 (약 2-3분)
2. Frontend: npm 패키지 설치 + React 빌드 (약 5-10분)

**로그 확인:**
```bash
# 전체 로그
docker-compose logs -f

# Backend만
docker-compose logs -f backend

# Frontend만
docker-compose logs -f frontend
```

#### G. 실행 확인

```bash
# 컨테이너 상태 확인
docker-compose ps

# Backend API 확인
curl http://localhost:8000/health
curl http://localhost:8000/docs

# Frontend 확인
curl http://localhost

# 분석 API 테스트 (샘플 데이터가 있는 경우)
curl -X POST http://localhost:8000/api/analysis/summarize/1
curl -X POST http://localhost:8000/api/analysis/keywords/1
curl -X POST http://localhost:8000/api/analysis/interview-questions/1
```

---

## 🔧 문제 해결

### 1. PostgreSQL 연결 실패

**증상:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**해결:**

```bash
# 1. 네트워크 연결 확인
docker exec backend ping <postgres-container-name>

# 2. .env 파일 확인
docker exec backend cat /app/.env

# 3. PostgreSQL 컨테이너 상태 확인
docker ps | grep postgres

# 4. 같은 네트워크에 있는지 확인
docker network inspect <network-name>
```

### 2. Ollama 연결 실패

**증상:**
```
httpx.ConnectError: Connection refused
```

**해결:**

```bash
# 1. Ollama 컨테이너 확인
docker ps | grep ollama

# 2. Ollama API 테스트
docker exec backend curl http://<ollama-container-name>:11434/api/version

# 3. .env 파일의 OLLAMA_BASE_URL 확인
```

### 3. 빌드 중 패키지 설치 실패

**증상:**
```
ERROR: Could not find a version that satisfies the requirement xxx
```

**해결:**

```bash
# python-packages/ 디렉토리 확인
ls python-packages/

# 누락된 패키지가 있다면 인터넷 환경에서 다시 다운로드:
pip download <package-name> -d python-packages/
```

### 4. Frontend 빌드 실패 (npm)

**증상:**
```
npm ERR! network request failed
```

**원인:** Frontend는 빌드 시 인터넷이 필요합니다 (npm 패키지 다운로드)

**해결 방법 1: 인터넷 환경에서 미리 빌드**
```bash
# 인터넷 환경에서 Frontend 이미지 빌드 후 내보내기
docker build -t llmproject-frontend ./frontend
docker save -o frontend-image.tar llmproject-frontend

# 서버에서 이미지 로드
docker load -i frontend-image.tar
```

**해결 방법 2: node_modules 미리 준비**
```bash
# 인터넷 환경에서
cd frontend
npm ci
tar -czf node_modules.tar.gz node_modules/

# 서버에서
tar -xzf node_modules.tar.gz -C frontend/
```

### 5. .env 수정 후 재시작

```bash
# 환경 변수만 변경한 경우
docker-compose restart backend

# 소스 코드 변경한 경우
docker-compose up -d --build backend
```

---

## 📊 요약

### 인터넷 환경 (준비)
1. ✅ 베이스 이미지 3개 내보내기 (.tar)
2. ✅ Python 패키지 다운로드 (python-packages/)
3. ✅ 전체 파일 압축 (llmproject.tar.gz)

### 폐쇄망 서버 (배포)
1. ✅ 압축 해제
2. ✅ 베이스 이미지 로드
3. ✅ 환경 변수 설정 (.env)
4. ✅ 네트워크 연결 (필요 시)
5. ✅ 빌드 + 실행 (`docker-compose up -d --build`)

---

## 🔐 보안 권장사항

1. **기본 비밀번호 변경**
   ```bash
   # .env 파일에서
   DATABASE_URL=postgresql://admin:강력한비밀번호@postgres:5432/applicants_db
   ```

2. **포트 제한** (필요 시)
   ```yaml
   # docker-compose.yml
   ports:
     - "127.0.0.1:8000:8000"  # localhost만 허용
   ```

3. **네트워크 격리**
   - Backend, Frontend를 PostgreSQL, Ollama와 같은 네트워크에 배치
   - 외부 접근은 Frontend만 허용
