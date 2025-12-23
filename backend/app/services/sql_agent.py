"""
SQL Agent - 자연어 질의를 SQL로 변환하고 실행
PostgreSQL 데이터베이스 조회 및 결과 해석
Tool-based 아키텍처: Few-shot은 Agent 레벨에서 처리
"""
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select
from app.services.ollama_service import ollama_service
from app.models.applicant import Applicant


class SQLAgent:
    """자연어를 SQL로 변환하여 실행하는 에이전트"""

    def __init__(self):
        self.ollama = ollama_service

    async def execute_query(self, query: str, session: Session) -> Dict[str, Any]:
        """
        자연어 질의를 SQL로 변환하고 실행

        Tool-based 아키텍처에서는 Few-shot이 Agent 레벨에서 처리됩니다.

        Args:
            query: 사용자 질의
            session: 데이터베이스 세션

        Returns:
            실행 결과 및 자연어 답변
        """
        # 1. 자연어 -> SQL 변환
        sql_info = await self._generate_sql(query)

        # 2. SQL 실행
        try:
            results = self._execute_sql(sql_info, session)
        except Exception as e:
            return {
                "answer": f"쿼리 실행 중 오류가 발생했습니다: {str(e)}",
                "sql": sql_info.get("sql", ""),
                "error": str(e)
            }

        # 3. 결과를 자연어로 해석
        answer = await self._interpret_results(query, results)

        return {
            "answer": answer,
            "sql": sql_info.get("sql", ""),
            "results": results,
            "count": len(results)
        }

    async def _generate_sql(self, query: str) -> Dict[str, str]:
        """
        자연어를 SQL로 변환

        Tool-based 아키텍처에서는 Few-shot이 Agent 레벨에서 처리됩니다.
        """
        schema_info = """
테이블: applicant_info
컬럼:
- id (BIGSERIAL): 지원자 ID
- reason (VARCHAR): 지원 동기
- experience (VARCHAR): 경력 및 경험
- skill (VARCHAR): 기술 스택 및 역량
"""

        prompt = f"""다음 데이터베이스 스키마를 참고하여 자연어 질의를 SQL로 변환해주세요.

{schema_info}

자연어 질의: {query}

SQL 쿼리만 작성하세요 (SELECT 문):"""

        sql = await self.ollama.generate(prompt)

        # SQL 정제 (주석, 설명 제거)
        sql_lines = [line.strip() for line in sql.split('\n') if line.strip() and not line.strip().startswith('--')]
        clean_sql = ' '.join(sql_lines)

        return {"sql": clean_sql}

    def _execute_sql(self, sql_info: Dict[str, str], session: Session) -> List[Dict[str, Any]]:
        """
        간단한 SQL 실행 (보안을 위해 제한적으로 구현)

        현재는 미리 정의된 쿼리 패턴만 지원
        실제 운영에서는 더 정교한 SQL 파싱 및 검증 필요
        """
        query_lower = sql_info.get("sql", "").lower()

        # 단순 전체 조회
        if "select" in query_lower and "from applicant_info" in query_lower:
            # 제한적 실행: 최대 10개만 조회
            statement = select(Applicant).limit(10)
            applicants = session.exec(statement).all()

            return [
                {
                    "id": app.id,
                    "reason": app.reason[:100] + "..." if app.reason and len(app.reason) > 100 else app.reason,
                    "experience": app.experience[:100] + "..." if app.experience and len(app.experience) > 100 else app.experience,
                    "skill": app.skill[:100] + "..." if app.skill and len(app.skill) > 100 else app.skill
                }
                for app in applicants
            ]

        # COUNT 쿼리
        elif "count" in query_lower:
            statement = select(Applicant)
            count = len(session.exec(statement).all())
            return [{"count": count}]

        # ID로 조회
        elif "where id" in query_lower or "id =" in query_lower:
            # ID 추출 (간단한 패턴)
            import re
            match = re.search(r'id\s*=\s*(\d+)', query_lower)
            if match:
                applicant_id = int(match.group(1))
                applicant = session.get(Applicant, applicant_id)
                if applicant:
                    return [{
                        "id": applicant.id,
                        "reason": applicant.reason,
                        "experience": applicant.experience,
                        "skill": applicant.skill
                    }]

        return []

    async def _interpret_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        SQL 실행 결과를 자연어로 해석

        Tool-based 아키텍처에서는 Few-shot이 Agent 레벨에서 처리됩니다.
        """
        if not results:
            return "조회 결과가 없습니다."

        # 결과 요약
        result_summary = str(results)[:500]  # 최대 500자

        prompt = f"""다음 데이터베이스 조회 결과를 사용자 질문에 맞게 자연어로 설명해주세요.

질문: {query}

조회 결과:
{result_summary}

자연어 답변:"""

        answer = await self.ollama.generate(prompt)
        return answer


# 싱글톤 인스턴스
sql_agent = SQLAgent()
