"""
RAG Chain - LangChain LCEL 구현
기존 RAGService를 LangChain으로 재구현 (200줄 → 50줄)
"""
import os
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_ollama import OllamaLLM
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

from app.models.few_shot import FewShot


class RAGChain:
    """
    LangChain LCEL 기반 RAG Chain

    Phase 1 RAGService와 동일한 기능:
    - Qdrant 벡터 검색
    - Few-shot 예제 주입
    - Ollama LLM 답변 생성
    - LangSmith 자동 추적
    """

    def __init__(
        self,
        ollama_base_url: str = None,
        qdrant_url: str = None,
        collection_name: str = "documents",
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    ):
        # 환경 변수에서 설정 로드
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.collection_name = collection_name or os.getenv("QDRANT_COLLECTION_NAME", "documents")
        self.embedding_model_name = embedding_model or os.getenv("EMBEDDING_MODEL")

        # LangChain Ollama LLM
        self.llm = OllamaLLM(
            base_url=self.ollama_base_url,
            model=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            temperature=0.7
        )

        # FastEmbed (Phase 1과 동일한 임베딩 모델 사용)
        fastembed_cache = os.getenv("FASTEMBED_CACHE_PATH", "/app/fastembed_cache")
        self.embedding = TextEmbedding(
            model_name=self.embedding_model_name,
            cache_dir=fastembed_cache
        )

        # Qdrant Client 및 Vector Store
        self.qdrant_client = QdrantClient(url=self.qdrant_url)
        self.vectorstore = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=self.collection_name,
            embedding=self.embedding
        )

        # Few-shot 프롬프트 템플릿 (Phase 1과 동일한 구조)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 문서 검색 기반 질의응답 AI입니다.
검색된 문서를 바탕으로 정확하고 간결하게 답변하세요.

{few_shot_examples}

검색된 문서:
{context}
"""),
            ("human", "{question}")
        ])

        # LCEL Chain 구성 (Runnable 파이프라인)
        self.chain = (
            {
                "context": RunnableLambda(self._format_docs),
                "question": RunnablePassthrough(),
                "few_shot_examples": RunnableLambda(lambda x: "")  # 기본값
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )

    def _format_docs(self, docs: List[Any]) -> str:
        """검색된 문서를 컨텍스트 문자열로 변환"""
        if not docs:
            return "검색된 문서가 없습니다."

        formatted = []
        for i, doc in enumerate(docs, 1):
            # LangChain Document 객체 또는 dict 모두 지원
            content = doc.page_content if hasattr(doc, 'page_content') else doc.get('text', '')
            formatted.append(f"[문서 {i}]\n{content}")

        return "\n\n".join(formatted)

    def _get_active_fewshots(self, session: Optional[Session], intent_type: str = "rag_search") -> str:
        """
        Few-shot 예제 조회 (Phase 1과 동일한 로직)

        Args:
            session: DB 세션
            intent_type: Intent 타입

        Returns:
            포맷팅된 Few-shot 예제 문자열
        """
        if not session:
            return ""

        few_shots = session.exec(
            select(FewShot)
            .where(FewShot.is_active == True)
            .where(FewShot.intent_type == intent_type)
            .order_by(FewShot.created_at.desc())
            .limit(3)  # 최대 3개
        ).all()

        if not few_shots:
            return ""

        examples = []
        for fs in few_shots:
            examples.append(f"예시 질문: {fs.user_query}\n예시 답변: {fs.expected_response}")

        return "참고할 예시:\n" + "\n\n".join(examples) + "\n"

    async def invoke(
        self,
        question: str,
        session: Optional[Session] = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        RAG Chain 실행 (Phase 1 answer_question과 동일한 인터페이스)

        Args:
            question: 사용자 질문
            session: DB 세션 (Few-shot 조회용)
            top_k: 검색할 문서 개수

        Returns:
            답변 및 참조 문서 정보
        """
        # 1. Qdrant 벡터 검색
        docs = self.vectorstore.similarity_search(question, k=top_k)

        if not docs:
            return {
                "answer": "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                "sources": [],
                "has_sources": False
            }

        # 2. Few-shot 예제 가져오기
        few_shot_examples = self._get_active_fewshots(session, intent_type="rag_search")

        # 3. LCEL Chain 실행 (LangSmith 자동 추적!)
        answer = await self.chain.ainvoke({
            "docs": docs,  # _format_docs에서 처리
            "question": question,
            "few_shot_examples": few_shot_examples
        })

        # 4. 결과 반환 (Phase 1과 동일한 형식)
        return {
            "answer": answer,
            "sources": [
                {
                    "text": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "score": doc.metadata.get("score", 0.0) if hasattr(doc, 'metadata') else 0.0,
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {}
                }
                for doc in docs
            ],
            "has_sources": True
        }


# 싱글톤 인스턴스 (Phase 1과 동일한 패턴)
_rag_chain_instance = None


def get_rag_chain() -> RAGChain:
    """RAG Chain 싱글톤 인스턴스 반환"""
    global _rag_chain_instance

    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()

    return _rag_chain_instance
