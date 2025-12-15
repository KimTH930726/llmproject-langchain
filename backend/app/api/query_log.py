"""질의 로그 API 엔드포인트"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, or_
from typing import Optional
from ..database import get_session
from ..models.query_log import (
    QueryLog,
    QueryLogCreate,
    QueryLogResponse,
    QueryLogListResponse,
    ConvertToFewShotRequest
)
from ..models.few_shot import FewShot, FewShotCreate

router = APIRouter(prefix="/api/query-logs", tags=["QueryLogs"])


@router.post("/", response_model=QueryLogResponse)
async def create_query_log(
    data: QueryLogCreate,
    session: Session = Depends(get_session)
):
    """
    질의 로그 생성 (자동 호출용)
    - 사용자 질의가 처리될 때마다 자동으로 호출
    """
    query_log = QueryLog(**data.model_dump())
    session.add(query_log)
    session.commit()
    session.refresh(query_log)
    return query_log


@router.get("/", response_model=QueryLogListResponse)
async def get_query_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    intent: Optional[str] = Query(None, description="Intent 타입 필터"),
    converted_only: bool = Query(False, description="Few-shot으로 변환된 것만 보기"),
    search: Optional[str] = Query(None, description="질의 텍스트 검색"),
    session: Session = Depends(get_session)
):
    """
    질의 로그 목록 조회
    - 최신순 정렬
    - 필터: intent, converted_only, search
    """
    # 기본 쿼리
    statement = select(QueryLog)

    # 필터 적용
    if intent:
        statement = statement.where(QueryLog.detected_intent == intent)

    if converted_only:
        statement = statement.where(QueryLog.is_converted_to_fewshot == True)

    if search:
        statement = statement.where(QueryLog.query_text.contains(search))

    # 전체 개수
    count_statement = select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()

    # 페이징 및 정렬
    statement = statement.order_by(QueryLog.created_at.desc()).offset(skip).limit(limit)
    results = session.exec(statement).all()

    return QueryLogListResponse(total=total, items=results)


@router.get("/{log_id}", response_model=QueryLogResponse)
async def get_query_log(
    log_id: int,
    session: Session = Depends(get_session)
):
    """질의 로그 단건 조회"""
    query_log = session.get(QueryLog, log_id)
    if not query_log:
        raise HTTPException(status_code=404, detail="Query log not found")
    return query_log


@router.post("/convert-to-fewshot")
async def convert_to_fewshot(
    data: ConvertToFewShotRequest,
    session: Session = Depends(get_session)
):
    """
    질의 로그를 Few-shot 예제로 승격
    - query_log의 is_converted_to_fewshot을 True로 변경
    - few_shots에 새 레코드 생성 (source_query_log_id 연결)
    """
    # 1. Query log 조회
    query_log = session.get(QueryLog, data.query_log_id)
    if not query_log:
        raise HTTPException(status_code=404, detail="Query log not found")

    # 2. 이미 변환되었는지 확인
    if query_log.is_converted_to_fewshot:
        raise HTTPException(status_code=400, detail="Already converted to few-shot")

    # 3. 동일한 질의 텍스트가 이미 Few-shot에 존재하는지 확인
    existing_fewshot = session.exec(
        select(FewShot).where(FewShot.user_query == query_log.query_text)
    ).first()
    if existing_fewshot:
        raise HTTPException(
            status_code=400,
            detail=f"Few-shot with same query already exists (ID: {existing_fewshot.id})"
        )

    # 4. Few-shot 생성
    few_shot = FewShot(
        source_query_log_id=data.query_log_id,
        intent_type=data.intent_type or query_log.detected_intent,
        user_query=query_log.query_text,
        expected_response=data.expected_response or query_log.response,
        is_active=data.is_active
    )
    session.add(few_shot)

    # 5. Query log 업데이트
    query_log.is_converted_to_fewshot = True
    session.add(query_log)

    session.commit()
    session.refresh(few_shot)

    return {
        "message": "Successfully converted to few-shot",
        "few_shot_id": few_shot.id,
        "query_log_id": data.query_log_id
    }


@router.delete("/{log_id}")
async def delete_query_log(
    log_id: int,
    session: Session = Depends(get_session)
):
    """질의 로그 삭제"""
    query_log = session.get(QueryLog, log_id)
    if not query_log:
        raise HTTPException(status_code=404, detail="Query log not found")

    # Few-shot으로 변환된 경우 삭제 불가 (데이터 무결성)
    if query_log.is_converted_to_fewshot:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete query log that has been converted to few-shot. Delete the few-shot first."
        )

    session.delete(query_log)
    session.commit()
    return {"message": "Query log deleted successfully"}


@router.get("/stats/summary")
async def get_query_log_stats(
    session: Session = Depends(get_session)
):
    """
    질의 로그 통계
    - 전체 개수
    - Intent 타입별 개수
    - Few-shot 변환률
    """
    total = session.exec(select(func.count()).select_from(QueryLog)).one()
    converted = session.exec(
        select(func.count()).select_from(QueryLog).where(QueryLog.is_converted_to_fewshot == True)
    ).one()

    # Intent 타입별 개수
    intent_stats_statement = select(
        QueryLog.detected_intent,
        func.count(QueryLog.id).label("count")
    ).group_by(QueryLog.detected_intent)
    intent_stats = session.exec(intent_stats_statement).all()

    return {
        "total_queries": total,
        "converted_to_fewshot": converted,
        "conversion_rate": round(converted / total * 100, 2) if total > 0 else 0,
        "by_intent": [{"intent": intent or "unknown", "count": count} for intent, count in intent_stats]
    }
