"""
RAG (Retrieval-Augmented Generation) 서비스
Qdrant에서 관련 문서를 검색하고 Ollama LLM으로 답변 생성
"""
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.services.qdrant_service import qdrant_service
from app.services.ollama_service import ollama_service
from app.models.few_shot import FewShot


class RAGService:
    """RAG 기반 질의응답 서비스"""

    def __init__(self):
        self.qdrant = qdrant_service
        self.ollama = ollama_service

    async def answer_question(
        self,
        question: str,
        top_k: int = 3,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        질문에 대해 RAG 방식으로 답변 생성

        Args:
            question: 사용자 질문
            top_k: 검색할 관련 문서 개수
            session: DB 세션 (Few-shot 예제 조회용, optional)

        Returns:
            답변 및 참조 문서 정보
        """
        # 1. Qdrant에서 관련 문서 검색
        search_results = self.qdrant.search(query=question, limit=top_k)

        if not search_results:
            return {
                "answer": "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                "sources": [],
                "has_sources": False
            }

        # 2. 검색된 문서를 컨텍스트로 결합
        context = self._build_context(search_results)

        # 3. Few-shot 예제 가져오기 (session이 제공된 경우)
        few_shots = self._get_active_fewshots(session, intent_type="rag_search") if session else []

        # 4. LLM 프롬프트 생성 및 답변 생성
        prompt = self._build_prompt(question, context, few_shots)
        answer = await self.ollama.generate(prompt)

        # 5. 결과 반환
        return {
            "answer": answer,
            "sources": [
                {
                    "text": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
                    "score": result["score"],
                    "metadata": result["metadata"]
                }
                for result in search_results
            ],
            "has_sources": True
        }

    async def answer_question_with_analysis(
        self,
        original_query: str,
        search_query: str,
        top_k: int = 3,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        질문에 대해 RAG 방식으로 답변 생성 + 연관성 분석 포함

        Args:
            original_query: 원본 사용자 질의
            search_query: 검색용 질의 (비정형 질의)
            top_k: 검색할 관련 문서 개수
            session: DB 세션 (Few-shot 예제 조회용, optional)

        Returns:
            답변, 참조 문서, 연관성 분석 정보
        """
        # 1. Qdrant에서 관련 문서 검색
        search_results = self.qdrant.search(query=search_query, limit=top_k)

        if not search_results:
            return {
                "answer": "관련 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요.",
                "sources": [],
                "has_sources": False,
                "relevance_analysis": {
                    "reasoning": "검색된 문서가 없어 분석 불가",
                    "confidence": 0.0,
                    "matched_sections": []
                }
            }

        # 2. 검색된 문서를 컨텍스트로 결합
        context = self._build_context(search_results)

        # 3. Few-shot 예제 가져오기
        few_shots = self._get_active_fewshots(session, intent_type="rag_search") if session else []

        # 4. LLM 프롬프트 생성 및 답변 생성
        prompt = self._build_prompt(search_query, context, few_shots)
        answer = await self.ollama.generate(prompt)

        # 5. 연관성 분석 (원본 질의와 검색 결과의 관계)
        relevance_analysis = await self._analyze_relevance(
            original_query=original_query,
            search_query=search_query,
            search_results=search_results,
            answer=answer
        )

        # 6. 결과 반환
        return {
            "answer": answer,
            "sources": [
                {
                    "text": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
                    "score": result["score"],
                    "metadata": result["metadata"]
                }
                for result in search_results
            ],
            "has_sources": True,
            "relevance_analysis": relevance_analysis
        }

    async def _analyze_relevance(
        self,
        original_query: str,
        search_query: str,
        search_results: List[Dict[str, Any]],
        answer: str
    ) -> Dict[str, Any]:
        """
        검색 결과와 원본 질의의 연관성 분석

        Args:
            original_query: 원본 사용자 질의
            search_query: 검색에 사용된 질의
            search_results: Qdrant 검색 결과
            answer: 생성된 답변

        Returns:
            연관성 분석 결과
        """
        prompt = f"""다음 질의에 대한 RAG 검색 결과를 분석하여 연관성을 설명하세요.

# 원본 사용자 질의
"{original_query}"

# 검색에 사용된 질의
"{search_query}"

# 검색된 문서 개수
{len(search_results)}개

# 검색 점수 (상위 3개)
{self._format_scores(search_results[:3])}

# 생성된 답변
"{answer}"

# 지시사항
1. 왜 이 검색 결과가 사용자 질의에 대한 답변으로 적합한지 설명
2. 검색 점수와 문서 내용을 바탕으로 신뢰도 평가 (0.0~1.0)
3. 답변에 사용된 주요 문서 섹션 나열

# 응답 형식 (JSON만 출력)
{{
  "reasoning": "연관성 설명 (왜 이 답변이 나왔는지)",
  "confidence": 0.0~1.0 사이 신뢰도 점수,
  "matched_sections": ["사용된 문서 섹션1", "섹션2", ...]
}}

응답:"""

        try:
            response = await self.ollama.generate(prompt)
            # JSON 파싱
            import json
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
                if response.startswith("json"):
                    response = response[4:].strip()

            parsed = json.loads(response)
            return {
                "reasoning": parsed.get("reasoning", ""),
                "confidence": float(parsed.get("confidence", 0.5)),
                "matched_sections": parsed.get("matched_sections", [])
            }
        except Exception as e:
            print(f"연관성 분석 파싱 실패: {e}")
            # 기본 분석 반환
            avg_score = sum(r["score"] for r in search_results) / len(search_results) if search_results else 0
            return {
                "reasoning": f"검색된 {len(search_results)}개 문서의 평균 유사도: {avg_score:.2f}",
                "confidence": avg_score,
                "matched_sections": [f"문서 {i+1}" for i in range(min(3, len(search_results)))]
            }

    def _format_scores(self, results: List[Dict[str, Any]]) -> str:
        """검색 점수를 보기 좋게 포맷"""
        return "\n".join([
            f"- 문서 {i+1}: {r['score']:.3f}"
            for i, r in enumerate(results)
        ])

    def _build_context(self, search_results: List[Dict[str, Any]]) -> str:
        """검색 결과를 컨텍스트 문자열로 결합"""
        contexts = []
        for idx, result in enumerate(search_results, 1):
            contexts.append(f"[문서 {idx}]\n{result['text']}\n")
        return "\n".join(contexts)

    def _get_active_fewshots(
        self,
        session: Optional[Session],
        intent_type: Optional[str] = None
    ) -> List[FewShot]:
        """
        활성화된 Few-shot 예제 조회

        Args:
            session: DB 세션
            intent_type: Intent 타입 필터 (optional)

        Returns:
            활성화된 Few-shot 예제 리스트
        """
        if not session:
            return []

        try:
            statement = select(FewShot).where(FewShot.is_active == True)
            if intent_type:
                statement = statement.where(FewShot.intent_type == intent_type)

            results = session.exec(statement).all()
            return list(results)
        except Exception as e:
            print(f"Few-shot 조회 실패: {e}")
            return []

    def _build_prompt(
        self,
        question: str,
        context: str,
        few_shots: List[FewShot] = None
    ) -> str:
        """RAG 프롬프트 생성 (Few-shot 예제 포함)"""
        prompt_parts = []

        # Few-shot 예제 추가
        if few_shots:
            prompt_parts.append("다음은 질문-답변 예제입니다:\n")
            for idx, fs in enumerate(few_shots, 1):
                prompt_parts.append(f"예제 {idx}:")
                prompt_parts.append(f"질문: {fs.user_query}")
                if fs.expected_response:
                    prompt_parts.append(f"답변: {fs.expected_response}")
                prompt_parts.append("")
            prompt_parts.append("---\n")

        # 기본 프롬프트
        prompt_parts.append("""다음 문서들을 참고하여 질문에 답변해주세요.
문서에 없는 내용은 추측하지 말고, 문서 내용을 바탕으로만 답변하세요.

참고 문서:""")
        prompt_parts.append(context)
        prompt_parts.append(f"\n질문: {question}\n")
        prompt_parts.append("답변:")

        return "\n".join(prompt_parts)


# 싱글톤 인스턴스
rag_service = RAGService()
