"""
Query Decomposition 서비스
사용자 질의를 비정형/정형 데이터로 분해하고 분류 사유 제공
"""
from typing import Dict, Any, Optional
import json
from app.services.ollama_service import ollama_service


class QueryDecomposer:
    """질의 분해 및 분류 서비스"""

    def __init__(self):
        self.ollama = ollama_service

    async def decompose_query(self, original_query: str) -> Dict[str, Any]:
        """
        사용자 질의를 비정형/정형으로 분해

        Args:
            original_query: 원본 사용자 질의

        Returns:
            {
                "unstructured_query": "비정형 질의 (문맥 기반)",
                "structured_query": "정형 질의 (구조화된 데이터 추출)",
                "needs_db_query": true/false,
                "decomposition_reasoning": "분류 사유"
            }
        """
        prompt = self._build_decomposition_prompt(original_query)
        response = await self.ollama.generate(prompt)

        # LLM 응답 파싱
        try:
            result = self._parse_decomposition_response(response)
            return result
        except Exception as e:
            # 파싱 실패 시 기본값 반환
            print(f"Query decomposition 파싱 실패: {e}")
            return {
                "unstructured_query": original_query,
                "structured_query": None,
                "needs_db_query": False,
                "decomposition_reasoning": "LLM 응답 파싱 실패로 기본 처리"
            }

    def _build_decomposition_prompt(self, query: str) -> str:
        """질의 분해를 위한 프롬프트 생성"""
        return f"""다음 사용자 질의를 분석하여 비정형 데이터와 정형 데이터 질의로 분해하세요.

# 정의
- **비정형 질의**: 문맥, 이유, 배경, 설명 등 문서의 자연어 내용을 이해해야 답변 가능한 질문
- **정형 질의**: 금액, 날짜, 이름, 수량 등 문서 내 구조화된 필드값을 추출하면 답변 가능한 질문
- **DB 쿼리 필요**: 문서가 아닌 데이터베이스 테이블에서 조회해야 하는 질문 (예: 통계, 집계, 최근 N개월 데이터)

# 사용자 질의
"{query}"

# 지시사항
1. 위 질의가 비정형/정형 중 어떤 유형인지 판단
2. 비정형 질의가 포함된 경우, 문맥 검색에 적합한 형태로 재구성
3. 정형 질의가 포함된 경우, 추출해야 할 필드/값을 명확히 표현
4. DB 쿼리가 필요한지 판단 (문서 검색으로 해결 불가능한 경우)
5. 왜 그렇게 분류했는지 사유 작성

# 응답 형식 (JSON만 출력, 다른 텍스트 포함 금지)
{{
  "unstructured_query": "비정형 질의 내용 (없으면 null)",
  "structured_query": "정형 질의 내용 (없으면 null)",
  "needs_db_query": true 또는 false,
  "decomposition_reasoning": "분류 사유 설명"
}}

응답:"""

    def _parse_decomposition_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출 및 파싱"""
        # JSON 블록 추출 시도
        response = response.strip()

        # ``` 코드 블록 제거
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
            if response.startswith("json"):
                response = response[4:].strip()

        # JSON 파싱
        parsed = json.loads(response)

        # 필수 필드 검증 및 기본값 설정
        return {
            "unstructured_query": parsed.get("unstructured_query"),
            "structured_query": parsed.get("structured_query"),
            "needs_db_query": parsed.get("needs_db_query", False),
            "decomposition_reasoning": parsed.get("decomposition_reasoning", "")
        }


# 싱글톤 인스턴스
query_decomposer = QueryDecomposer()
