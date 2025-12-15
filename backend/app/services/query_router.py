"""
QueryRouter - 사용자 질의의 의도를 분류하는 서비스
RAG 검색 vs SQL 쿼리를 판단
"""
from enum import Enum
from typing import Optional, List, Set
from sqlmodel import Session, select, text
from app.services.ollama_service import ollama_service
from app.models.few_shot import Intent


class QueryIntent(str, Enum):
    """질의 의도 타입"""
    RAG_SEARCH = "rag_search"  # 문서 검색 기반 답변
    SQL_QUERY = "sql_query"    # 데이터베이스 쿼리 기반 답변
    GENERAL = "general"        # 일반 대화


class QueryRouter:
    """사용자 질의를 분석하여 적절한 처리 방식을 결정"""

    def __init__(self):
        self.ollama = ollama_service

    async def classify_intent(self, query: str, intent_candidates: Optional[List[str]] = None) -> QueryIntent:
        """
        질의를 분석하여 의도 분류

        Args:
            query: 사용자 질의
            intent_candidates: intent 테이블에서 매칭된 의도 후보들 (애매한 경우)

        Returns:
            QueryIntent (rag_search, sql_query, general)
        """
        # LLM을 사용한 의도 분류
        prompt_parts = []

        # 의도 후보가 있으면 프롬프트에 포함
        if intent_candidates:
            prompt_parts.append(f"다음 질문은 키워드 매칭 결과 여러 의도로 해석될 수 있습니다.")
            prompt_parts.append(f"의도 후보: {', '.join(intent_candidates)}")
            prompt_parts.append(f"이 후보들을 참고하여 가장 적합한 의도를 선택해주세요.\n")

        prompt_parts.append("""다음 질문의 유형을 분류해주세요.

질문 유형:
1. rag_search: 문서 내용 검색이 필요한 질문 (예: "계약서 내용이 뭐야?", "문서에서 금액은?")
2. sql_query: 데이터베이스 조회가 필요한 질문 (예: "지원자 목록 보여줘", "지원자 수는?", "ID 1번 지원자 정보")
3. general: 일반 대화 (예: "안녕", "고마워", "어떻게 사용해?")""")

        prompt_parts.append(f"\n질문: {query}")
        prompt_parts.append("\n위 질문의 유형을 rag_search, sql_query, general 중 하나만 답하세요:")

        prompt = "\n".join(prompt_parts)
        response = await self.ollama.generate(prompt)
        response_lower = response.strip().lower()

        # 응답에서 의도 추출
        if "sql" in response_lower or "sql_query" in response_lower:
            return QueryIntent.SQL_QUERY
        elif "rag" in response_lower or "rag_search" in response_lower:
            return QueryIntent.RAG_SEARCH
        else:
            return QueryIntent.GENERAL

    async def classify_intent_simple(self, query: str, session: Optional[Session] = None) -> QueryIntent:
        """
        Two-tier 의도 분류:
        1. intents 테이블에서 키워드 매칭 확인 (우선)
           - 1개 매칭: 즉시 반환
           - 2개 이상 매칭: 의도 후보로 LLM에 전달
        2. 매칭 안되면 LLM으로 분류 (fallback)

        Args:
            query: 사용자 질의
            session: DB 세션 (intents 테이블 조회용)

        Returns:
            QueryIntent
        """
        # 1단계: intents 테이블에서 키워드 매칭
        intent_candidates = []
        if session:
            result = self._check_intent_table(query, session)
            if isinstance(result, QueryIntent):
                # 1개만 매칭됨 - 즉시 반환
                return result
            elif isinstance(result, list):
                # 2개 이상 매칭됨 - 의도 후보로 저장
                intent_candidates = result

        # 2단계: LLM 기반 의도 분류 (fallback 또는 애매한 경우)
        return await self.classify_intent(query, intent_candidates=intent_candidates if intent_candidates else None)

    def _check_intent_table(self, query: str, session: Session):
        """
        intents 테이블에서 키워드 매칭 확인 (DB 레벨 필터링)

        로직: query 문자열에 keyword가 포함되는지 확인
        예: keyword="몇명" → query="지원자 몇명이야?" ✓ 매칭

        Args:
            query: 사용자 질의
            session: DB 세션

        Returns:
            - QueryIntent: 1개만 매칭된 경우 (즉시 사용 가능)
            - List[str]: 2개 이상 매칭된 경우 (의도 후보들)
            - None: 매칭 없음
        """
        try:
            # PostgreSQL에서 query 문자열에 keyword가 포함되는지 확인
            # SQL: WHERE LOWER(:query) LIKE '%' || LOWER(keyword) || '%'
            # 예: LOWER('지원자 몇명이야') LIKE '%' || LOWER('몇명') || '%'
            query_lower = query.lower()

            # text() 함수로 원시 SQL 조건 사용
            statement = (
                select(Intent)
                .where(
                    text("LOWER(:query) LIKE '%' || LOWER(keyword) || '%'")
                    .bindparams(query=query_lower)
                )
                .order_by(Intent.priority.desc())
            )
            matched_intents = session.exec(statement).all()

            # 매칭된 intent가 없으면 None 반환
            if not matched_intents:
                return None

            # 유효한 intent_type만 수집 (중복 제거)
            matched_intent_types = []
            for intent in matched_intents:
                try:
                    QueryIntent(intent.intent_type)  # 유효성 검사
                    if intent.intent_type not in matched_intent_types:
                        matched_intent_types.append(intent.intent_type)
                except ValueError:
                    # 유효하지 않은 intent_type이면 무시
                    continue

            # 매칭 결과에 따라 반환
            if len(matched_intent_types) == 0:
                return None
            elif len(matched_intent_types) == 1:
                # 1개만 매칭 - 즉시 반환
                return QueryIntent(matched_intent_types[0])
            else:
                # 2개 이상 매칭 - 의도 후보 리스트 반환
                return matched_intent_types

        except Exception as e:
            print(f"Intent 테이블 조회 실패: {e}")
            return None


# 싱글톤 인스턴스
query_router = QueryRouter()
