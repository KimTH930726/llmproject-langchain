"""
SQL Agent - 자연어 질의를 SQL로 변환하고 실행
PostgreSQL 데이터베이스 조회 및 결과 해석
"""
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select
from app.services.ollama_service import ollama_service
from app.models.applicant import Applicant
from app.models.few_shot import FewShot


class SQLAgent:
    """자연어를 SQL로 변환하여 실행하는 에이전트"""

    def __init__(self):
        self.ollama = ollama_service

    async def execute_query(self, query: str, session: Session) -> Dict[str, Any]:
        """
        자연어 질의를 SQL로 변환하고 실행

        Args:
            query: 사용자 질의
            session: 데이터베이스 세션

        Returns:
            실행 결과 및 자연어 답변
        """
        # 1. Few-shot 예제 가져오기
        few_shots = self._get_active_fewshots(session, intent_type="sql_query")

        # 2. 자연어 -> SQL 변환 (Few-shot 포함)
        sql_info = await self._generate_sql(query, few_shots)

        # 3. SQL 실행
        try:
            results = self._execute_sql(sql_info, session)
        except Exception as e:
            return {
                "answer": f"쿼리 실행 중 오류가 발생했습니다: {str(e)}",
                "sql": sql_info.get("sql", ""),
                "error": str(e)
            }

        # 4. 결과를 자연어로 해석 (Few-shot 포함)
        answer = await self._interpret_results(query, results, few_shots)

        return {
            "answer": answer,
            "sql": sql_info.get("sql", ""),
            "results": results,
            "count": len(results)
        }

    def _get_active_fewshots(
        self,
        session: Optional[Session],
        intent_type: Optional[str] = None
    ) -> List[FewShot]:
        """Few-shot 예제 가져오기"""
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

    async def _generate_sql(self, query: str, few_shots: List[FewShot] = None) -> Dict[str, str]:
        """자연어를 SQL로 변환 (Few-shot 예제 포함)"""
        schema_info = """
테이블: applicant_info
컬럼:
- id (BIGSERIAL): 지원자 ID
- reason (VARCHAR): 지원 동기
- experience (VARCHAR): 경력 및 경험
- skill (VARCHAR): 기술 스택 및 역량
"""

        prompt_parts = []

        # Few-shot 예제 추가
        if few_shots:
            prompt_parts.append("다음은 질문-SQL 변환 예제입니다:\n")
            for idx, fs in enumerate(few_shots, 1):
                prompt_parts.append(f"예제 {idx}:")
                prompt_parts.append(f"질문: {fs.user_query}")
                if fs.expected_response:
                    prompt_parts.append(f"SQL: {fs.expected_response}")
                prompt_parts.append("")
            prompt_parts.append("---\n")

        # 기본 프롬프트
        prompt_parts.append(f"""다음 데이터베이스 스키마를 참고하여 자연어 질의를 SQL로 변환해주세요.

{schema_info}

자연어 질의: {query}

SQL 쿼리만 작성하세요 (SELECT 문):""")

        prompt = "\n".join(prompt_parts)
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

    async def _interpret_results(self, query: str, results: List[Dict[str, Any]], few_shots: List[FewShot] = None) -> str:
        """SQL 실행 결과를 자연어로 해석 (Few-shot 예제 포함)"""
        if not results:
            return "조회 결과가 없습니다."

        # 결과 요약
        result_summary = str(results)[:500]  # 최대 500자

        prompt_parts = []

        # Few-shot 예제 추가
        if few_shots:
            prompt_parts.append("다음은 결과 해석 예제입니다:\n")
            for idx, fs in enumerate(few_shots, 1):
                prompt_parts.append(f"예제 {idx}:")
                prompt_parts.append(f"질문: {fs.user_query}")
                if fs.expected_response:
                    prompt_parts.append(f"답변: {fs.expected_response}")
                prompt_parts.append("")
            prompt_parts.append("---\n")

        # 기본 프롬프트
        prompt_parts.append(f"""다음 데이터베이스 조회 결과를 사용자 질문에 맞게 자연어로 설명해주세요.

질문: {query}

조회 결과:
{result_summary}

자연어 답변:""")

        prompt = "\n".join(prompt_parts)
        answer = await self.ollama.generate(prompt)
        return answer


# 싱글톤 인스턴스
sql_agent = SQLAgent()
