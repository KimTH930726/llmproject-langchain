# Phase 2 프로젝트 시작 가이드

## 🎯 목표

**Phase 1 (현재)**: 커스텀 RAG 시스템 (폐쇄망 배포용, 경량화) ✅ **졸업!**

**Phase 2 (새 프로젝트)**: LangChain/LangGraph 기반 확장 버전
- 기존 프로젝트와 DB 호환성 유지
- Git 저장소는 완전히 별개로 관리
- LangSmith 무료 버전 사용

---

## 📋 Phase 2 시작 체크리스트

### 1단계: 새 Git 저장소 생성 (5분)

#### Option A: GitHub에서 생성 (권장)

```bash
# 1. GitHub에서 새 저장소 생성
# - 저장소 이름: llmproject-langchain (또는 원하는 이름)
# - Public/Private: 선택
# - README 추가 안함 (나중에 추가)

# 2. 로컬에서 저장소 URL 복사
# 예: https://github.com/your-username/llmproject-langchain.git
```

#### Option B: GitLab/Bitbucket 등 다른 서비스
```bash
# 동일하게 새 저장소 생성하고 URL 복사
```

---

### 2단계: 프로젝트 복사 및 Git 초기화 (5분)

```bash
# 1. 현재 프로젝트 디렉토리로 이동
cd /Users/kth

# 2. 새 프로젝트로 복사 (node_modules, __pycache__ 제외)
cp -r llmproject llmproject-langchain

# 3. 새 프로젝트로 이동
cd llmproject-langchain

# 4. 기존 Git 히스토리 제거
rm -rf .git

# 5. 새 Git 저장소 초기화
git init
git branch -M main

# 6. 새 원격 저장소 연결 (1단계에서 복사한 URL 사용)
git remote add origin https://github.com/your-username/llmproject-langchain.git

# 7. .gitignore 확인 (이미 존재함)
cat .gitignore

# 8. 첫 커밋 (Phase 1 코드 베이스)
git add .
git commit -m "Initial commit: Phase 1 codebase for LangChain migration

- Custom RAG implementation (RAGService, QueryRouter, SQL Agent)
- Two-Tier Intent Classification
- Few-shot Learning
- Multi-Stage RAG with Query Decomposition
- PostgreSQL + Qdrant + Ollama
- React frontend with management UI

Next: Migrate to LangChain/LangGraph"

# 9. GitHub에 푸시
git push -u origin main
```

**✅ 확인:** GitHub/GitLab에서 새 저장소에 코드가 업로드되었는지 확인

---

### 3단계: LangChain 의존성 추가 (5분)

```bash
# 1. backend/requirements.txt 열기
cd /Users/kth/llmproject-langchain/backend

# 2. 파일 끝에 LangChain 의존성 추가
cat >> requirements.txt << 'EOF'

# ==========================================
# Phase 2: LangChain/LangGraph Dependencies
# ==========================================
# LangChain Core
langchain==0.3.9
langchain-core==0.3.21
langchain-community==0.3.8

# LangGraph (Workflow Orchestration)
langgraph==0.2.50

# LangSmith (Tracing & Monitoring)
langsmith==0.1.145

# LangChain Integrations
langchain-ollama==0.2.0        # Ollama LLM
langchain-qdrant==0.2.0        # Qdrant Vector Store
langchain-experimental==0.3.3  # SQL Agent

# Additional Tools
tiktoken==0.7.0                # Token counting
jsonpatch==1.33                # JSON operations
EOF

# 3. 변경 사항 커밋
git add requirements.txt
git commit -m "Add LangChain/LangGraph dependencies for Phase 2"
git push
```

**예상 추가 크기:** ~50MB (LangChain 의존성)

---

### 4단계: LangSmith 설정 (10분)

#### 4.1. LangSmith 계정 생성

```bash
# 1. 브라우저에서 https://smith.langchain.com 접속
# 2. "Sign Up" 클릭
# 3. Google/GitHub 계정으로 로그인 (추천) 또는 이메일 가입
# 4. 무료 Developer 플랜 선택
```

#### 4.2. API 키 발급

```bash
# 1. LangSmith 대시보드 접속
# 2. 우측 상단 프로필 → "Settings" 클릭
# 3. 좌측 메뉴에서 "API Keys" 클릭
# 4. "Create API Key" 클릭
#    - Name: llmproject-langchain
#    - Description: Phase 2 Development
# 5. API 키 복사 (ls-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
#    ⚠️ 주의: 이 키는 다시 볼 수 없으므로 안전한 곳에 저장!
```

#### 4.3. 환경 변수 설정

```bash
# 1. backend/.env 파일 수정
cd /Users/kth/llmproject-langchain/backend

# 2. 기존 .env가 없으면 생성
cat > .env << 'EOF'
# ==========================================
# Phase 1: Original Environment Variables
# ==========================================
DATABASE_URL=postgresql://admin:admin123@postgres:5432/applicants_db
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=documents
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
FASTEMBED_CACHE_PATH=/app/fastembed_cache

# ==========================================
# Phase 2: LangChain/LangSmith
# ==========================================
# LangSmith Tracing (무료 Developer 플랜)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=ls-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LANGCHAIN_PROJECT=llmproject-phase2

# LangChain Settings
LANGCHAIN_VERBOSE=false
LANGCHAIN_CALLBACKS_BACKGROUND=true
EOF

# 3. API 키 수정 (위에서 복사한 키로 교체)
# vi .env 또는 nano .env 로 LANGCHAIN_API_KEY 수정

# 4. .env.example도 업데이트 (API 키는 제외)
cat > .env.example << 'EOF'
# Database
DATABASE_URL=postgresql://admin:admin123@postgres:5432/applicants_db

# LLM
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b

# Vector DB
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=documents

# Embedding
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
FASTEMBED_CACHE_PATH=/app/fastembed_cache

# LangSmith (Phase 2)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=llmproject-phase2
LANGCHAIN_VERBOSE=false
EOF

# 5. .gitignore에 .env가 있는지 확인 (민감 정보 보호)
grep -q "^.env$" ../.gitignore || echo ".env" >> ../.gitignore

# 6. 커밋
git add .env.example ../.gitignore
git commit -m "Add LangSmith configuration for Phase 2

- LangSmith API key setup
- Tracing enabled
- Project name: llmproject-phase2"
git push
```

**⚠️ 중요:** `.env` 파일은 절대 Git에 커밋하지 마세요! (API 키 유출 위험)

---

### 5단계: 로컬 개발 환경 테스트 (10분)

```bash
# 1. Phase 1 프로젝트 중지 (포트 충돌 방지)
cd /Users/kth/llmproject
docker-compose -f docker-compose.dev.yml down

# 2. Phase 2 프로젝트로 이동
cd /Users/kth/llmproject-langchain

# 3. Docker 네트워크 확인 (Phase 1과 동일한 네트워크 사용 가능)
docker network ls | grep llmproject-backend

# 없으면 생성
docker network create llmproject-backend

# 4. 전체 스택 시작 (PostgreSQL, Ollama, Qdrant, Backend, Frontend)
docker-compose -f docker-compose.dev.yml up -d

# 5. 로그 확인 (LangSmith 연결 확인)
docker-compose logs -f backend

# 예상 출력:
# backend  | INFO:     LangSmith tracing enabled
# backend  | INFO:     Project: llmproject-phase2
# backend  | INFO:     Started server process [1]

# 6. API 테스트
curl http://localhost:8000/docs

# 7. Frontend 접속
open http://localhost
```

**✅ 확인:**
- [ ] Backend API 문서 접속 가능 (http://localhost:8000/docs)
- [ ] Frontend 접속 가능 (http://localhost)
- [ ] 기존 기능 정상 작동 (채팅, 지원자 분석 등)
- [ ] LangSmith 대시보드에서 trace 확인 (https://smith.langchain.com)

---

### 6단계: Phase 2 README 작성 (10분)

```bash
cd /Users/kth/llmproject-langchain

cat > README.md << 'EOF'
# LLM 채용 지원자 분석 시스템 - Phase 2 (LangChain/LangGraph)

> **Phase 1에서 Phase 2로 진화**: 커스텀 RAG → LangChain/LangGraph 기반 고급 워크플로

## 🎯 Phase 2 목표

- ✅ LangChain LCEL로 RAG Chain 재구현
- ✅ LangGraph로 복잡한 워크플로 구현
- ✅ LangSmith로 추적 및 모니터링
- ✅ Phase 1 DB 스키마와 100% 호환

## 🏗️ 아키텍처

### Phase 1 (기존)
```
사용자 질의 → QueryRouter (커스텀) → RAGService/SQLAgent (커스텀) → Ollama
```

### Phase 2 (목표)
```
사용자 질의 → LangGraph ChatGraph → LangChain Chains → Ollama
                ↓
           LangSmith Tracing
```

## 🚀 빠른 시작

### 1. 환경 변수 설정
```bash
cp backend/.env.example backend/.env
# backend/.env에서 LANGCHAIN_API_KEY 수정
```

### 2. 전체 스택 실행
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 3. API 문서
http://localhost:8000/docs

### 4. LangSmith 대시보드
https://smith.langchain.com → Projects → llmproject-phase2

## 📚 문서

| 문서 | 설명 |
|------|------|
| [LANGCHAIN_MIGRATION_PLAN.md](LANGCHAIN_MIGRATION_PLAN.md) | 마이그레이션 계획 |
| [PHASE2_SETUP_GUIDE.md](PHASE2_SETUP_GUIDE.md) | 초기 설정 가이드 (현재 문서) |
| [CHAINS_GUIDE.md](docs/CHAINS_GUIDE.md) | LangChain Chains 구현 (작성 예정) |
| [GRAPHS_GUIDE.md](docs/GRAPHS_GUIDE.md) | LangGraph 워크플로 (작성 예정) |

## 🔗 Phase 1 프로젝트

Phase 1 커스텀 RAG 구현은 별도 저장소에서 관리됩니다.
- Phase 1: [기존 저장소 URL]
- Phase 2: [현재 저장소]

## 📊 마이그레이션 현황

- [x] Phase 1 코드베이스 복사
- [x] LangChain 의존성 추가
- [x] LangSmith 설정
- [ ] RAG Chain 구현 (진행 중)
- [ ] SQL Chain 구현
- [ ] ChatGraph 구현
- [ ] Hybrid Search Graph 구현

## 💡 주요 차이점

| 항목 | Phase 1 (커스텀) | Phase 2 (LangChain) |
|------|-----------------|-------------------|
| RAG 구현 | 직접 구현 (200줄) | LCEL Chain (50줄) |
| 워크플로 | if/else 분기 | LangGraph 시각화 |
| 디버깅 | print() | LangSmith 대시보드 |
| SQL Agent | 패턴 매칭 | LangChain SQL Agent |

## 📝 라이선스

MIT License
EOF

git add README.md
git commit -m "Add Phase 2 README with migration status"
git push
```

---

### 7단계: Phase 2 브랜치 전략 설정 (5분)

```bash
# 1. Feature 브랜치 생성
git checkout -b feature/langchain-core

# 2. 다음 단계부터는 이 브랜치에서 작업
# - Phase 2-1: RAG Chain 구현
# - Phase 2-2: SQL Chain 구현
# - Phase 2-3: ChatGraph 구현

# 3. 브랜치 푸시
git push -u origin feature/langchain-core
```

**브랜치 전략:**
```
main (Phase 1 코드베이스)
  └── feature/langchain-core (RAG/SQL Chains)
      └── feature/langgraph (Graphs)
          └── feature/hybrid-search (고급 기능)
```

---

## 🎓 Phase 1 졸업 체크리스트

### 완성된 기능 (Phase 1)
- [x] Two-Tier Intent Classification
- [x] Custom RAG Service
- [x] SQL Agent (자연어 → SQL)
- [x] Few-shot Learning
- [x] Multi-Stage RAG (Query Decomposition)
- [x] PostgreSQL Trigger Audit
- [x] Air-Gapped Deployment
- [x] FastEmbed 경량 임베딩
- [x] React Management UI

### 보존할 파일 (Phase 2에서도 유지)
```
backend/app/
├── models/           # ✅ 그대로 유지 (DB 스키마 호환)
├── database.py       # ✅ 그대로 유지
├── services/
│   └── legacy/       # ✅ Phase 1 서비스 보관 (참고용)
└── api/
    └── legacy/       # ✅ Phase 1 API 보관 (호환성)
```

---

## 📈 다음 단계 (Phase 2-1: LangChain Chains)

**목표:** RAGService를 LangChain LCEL Chain으로 재구현

**작업 내용:**
1. `backend/app/chains/rag_chain.py` 생성
2. LangChain Ollama, Qdrant 통합
3. Few-shot 프롬프트 템플릿 작성
4. `backend/app/api/chat.py`에서 RAGChain 사용
5. LangSmith에서 추적 확인

**예상 시간:** 3-4시간

**시작 명령:**
```bash
# feature/langchain-core 브랜치에서 작업
git checkout feature/langchain-core

# chains 디렉토리 생성
mkdir -p backend/app/chains
touch backend/app/chains/__init__.py
touch backend/app/chains/rag_chain.py

# 다음 가이드 참고: LANGCHAIN_MIGRATION_PLAN.md의 Phase 2.2
```

---

## 🆘 문제 해결

### 1. LangSmith 연결 실패
```bash
# 로그 확인
docker-compose logs backend | grep -i langsmith

# API 키 확인
docker exec backend env | grep LANGCHAIN

# 재시작
docker-compose restart backend
```

### 2. 포트 충돌 (Phase 1과 동시 실행 시)
```bash
# Phase 1 중지
cd /Users/kth/llmproject
docker-compose -f docker-compose.dev.yml down

# Phase 2 시작
cd /Users/kth/llmproject-langchain
docker-compose -f docker-compose.dev.yml up -d
```

### 3. DB 호환성 문제
```bash
# Phase 1과 Phase 2는 같은 PostgreSQL DB 사용 가능
# docker-compose.yml에서 동일한 외부 네트워크 사용
networks:
  dev-network:
    external: true
    name: llmproject-backend
```

---

## ✅ 설정 완료 확인

### 체크리스트
- [ ] 새 Git 저장소 생성 및 코드 푸시
- [ ] LangChain 의존성 추가
- [ ] LangSmith 계정 생성 및 API 키 발급
- [ ] 환경 변수 설정 (.env)
- [ ] Docker 컨테이너 실행
- [ ] API 문서 접속 (http://localhost:8000/docs)
- [ ] LangSmith 대시보드 접속 (https://smith.langchain.com)
- [ ] Phase 2 README 작성
- [ ] feature/langchain-core 브랜치 생성

### 모두 완료되면
```bash
echo "🎉 Phase 2 준비 완료! LangChain/LangGraph 구현 시작 가능"
echo "다음: LANGCHAIN_MIGRATION_PLAN.md의 Phase 2.2 (RAG Chain 구현)"
```

---

## 🎓 Phase 1 → Phase 2 전환 완료!

**Phase 1 (졸업)**: 커스텀 RAG로 핵심 개념 학습 ✅

**Phase 2 (시작)**: LangChain/LangGraph로 프로덕션 레벨 구현 🚀

질문이나 문제가 있으면 언제든지 물어보세요!
EOF

git add PHASE2_SETUP_GUIDE.md
git commit -m "Add Phase 2 setup guide for LangChain migration"
git push
```

---

## 🎉 준비 완료!

이제 다음 작업을 시작할 수 있습니다:

1. **GitHub에 새 저장소 생성**
   - 저장소 이름 예: `llmproject-langchain`
   - Public/Private 선택
   - README 추가 안함

2. **위 가이드 따라 실행**
   ```bash
   # 프로젝트 복사
   cd /Users/kth
   cp -r llmproject llmproject-langchain
   cd llmproject-langchain

   # Git 초기화
   rm -rf .git
   git init
   git remote add origin <새-저장소-URL>

   # 첫 커밋
   git add .
   git commit -m "Initial commit: Phase 1 codebase"
   git push -u origin main
   ```

3. **LangSmith 설정**
   - https://smith.langchain.com 접속
   - 계정 생성
   - API 키 발급

새 저장소 URL을 만드시면 알려주세요. 다음 단계로 바로 진행하겠습니다! 🚀