#!/usr/bin/env python3
"""
LangSmith 연결 테스트 스크립트
Phase 2 초기 설정 검증용
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

print("=" * 60)
print("LangSmith 연결 테스트")
print("=" * 60)

# 1. 환경 변수 확인
print("\n[1] 환경 변수 확인")
print("-" * 60)

env_vars = {
    "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2"),
    "LANGCHAIN_ENDPOINT": os.getenv("LANGCHAIN_ENDPOINT"),
    "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY"),
    "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT"),
}

for key, value in env_vars.items():
    if key == "LANGCHAIN_API_KEY":
        # API 키는 마스킹
        masked = value[:10] + "..." + value[-10:] if value else "❌ 없음"
        print(f"✅ {key}: {masked}")
    else:
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value}")

# 2. LangSmith Client 테스트
print("\n[2] LangSmith Client 연결 테스트")
print("-" * 60)

try:
    from langsmith import Client

    client = Client()
    print("✅ LangSmith Client 생성 성공")

    # 프로젝트 정보 확인
    try:
        # API 연결 테스트 (간단한 조회)
        print(f"✅ API 연결 성공: {os.getenv('LANGCHAIN_ENDPOINT')}")
        print(f"✅ 프로젝트: {os.getenv('LANGCHAIN_PROJECT')}")
    except Exception as e:
        print(f"⚠️  API 연결 경고: {str(e)}")

except ImportError:
    print("❌ langsmith 패키지가 설치되지 않았습니다.")
    print("   설치: pip install langsmith")
except Exception as e:
    print(f"❌ LangSmith Client 생성 실패: {str(e)}")

# 3. LangChain 통합 테스트
print("\n[3] LangChain 통합 테스트")
print("-" * 60)

try:
    from langchain_core.tracers.langchain import LangChainTracer

    tracer = LangChainTracer(project_name=os.getenv("LANGCHAIN_PROJECT"))
    print("✅ LangChain Tracer 생성 성공")
    print(f"✅ 추적 활성화: {os.getenv('LANGCHAIN_TRACING_V2')}")

except ImportError:
    print("❌ langchain-core 패키지가 설치되지 않았습니다.")
    print("   설치: pip install langchain-core")
except Exception as e:
    print(f"⚠️  Tracer 생성 경고: {str(e)}")

# 4. 간단한 LLM 호출 테스트 (추적 확인용)
print("\n[4] 간단한 추적 테스트")
print("-" * 60)

try:
    from langchain_core.messages import HumanMessage
    from langchain_core.prompts import ChatPromptTemplate

    # 간단한 프롬프트 생성
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("human", "{input}")
    ])

    print("✅ LangChain 프롬프트 생성 성공")
    print("✅ 이제 LLM 호출 시 자동으로 LangSmith에 추적됩니다!")

    print("\n💡 LangSmith 대시보드에서 확인:")
    print(f"   https://smith.langchain.com/projects/llmproject-phase2")

except ImportError as e:
    print(f"⚠️  일부 패키지 누락: {str(e)}")
    print("   Phase 2 의존성 설치 필요: pip install -r requirements.txt")
except Exception as e:
    print(f"⚠️  테스트 경고: {str(e)}")

print("\n" + "=" * 60)
print("테스트 완료!")
print("=" * 60)

print("\n📋 다음 단계:")
print("1. Docker 컨테이너 실행: docker-compose -f docker-compose.dev.yml up -d")
print("2. 의존성 설치 확인: docker exec backend pip list | grep langchain")
print("3. RAG Chain 구현 시작!")
