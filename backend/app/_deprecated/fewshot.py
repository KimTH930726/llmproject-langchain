"""Few-shot CRUD API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models.few_shot import (
    FewShot,
    FewShotResponse,
    FewShotCreate,
    FewShotUpdate,
    FewShotAudit,
    FewShotAuditResponse
)

router = APIRouter(prefix="/api/fewshot", tags=["Few-shot Management"])


# ===== Few-shot CRUD =====

@router.get("/", response_model=List[FewShotResponse])
async def get_all_fewshots(
    intent_type: Optional[str] = Query(None, description="Filter by intent type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: Session = Depends(get_session)
):
    """모든 Few-shot 목록 조회 (필터링 가능)."""
    statement = select(FewShot)

    if intent_type is not None:
        statement = statement.where(FewShot.intent_type == intent_type)
    if is_active is not None:
        statement = statement.where(FewShot.is_active == is_active)

    statement = statement.order_by(FewShot.created_at.desc())
    fewshots = session.exec(statement).all()
    return fewshots


@router.get("/{fewshot_id}", response_model=FewShotResponse)
async def get_fewshot(fewshot_id: int, session: Session = Depends(get_session)):
    """특정 Few-shot 조회."""
    fewshot = session.get(FewShot, fewshot_id)
    if not fewshot:
        raise HTTPException(status_code=404, detail=f"Few-shot with id {fewshot_id} not found")
    return fewshot


@router.post("/", response_model=FewShotResponse, status_code=201)
async def create_fewshot(fewshot_data: FewShotCreate, session: Session = Depends(get_session)):
    """Few-shot 생성."""
    fewshot = FewShot(**fewshot_data.model_dump())
    session.add(fewshot)
    session.commit()
    session.refresh(fewshot)
    return fewshot


@router.put("/{fewshot_id}", response_model=FewShotResponse)
async def update_fewshot(
    fewshot_id: int,
    fewshot_data: FewShotUpdate,
    session: Session = Depends(get_session)
):
    """Few-shot 수정."""
    fewshot = session.get(FewShot, fewshot_id)
    if not fewshot:
        raise HTTPException(status_code=404, detail=f"Few-shot with id {fewshot_id} not found")

    update_data = fewshot_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fewshot, key, value)

    session.add(fewshot)
    session.commit()
    session.refresh(fewshot)
    return fewshot


@router.delete("/{fewshot_id}", status_code=204)
async def delete_fewshot(fewshot_id: int, session: Session = Depends(get_session)):
    """Few-shot 삭제."""
    fewshot = session.get(FewShot, fewshot_id)
    if not fewshot:
        raise HTTPException(status_code=404, detail=f"Few-shot with id {fewshot_id} not found")

    # Few-shot 삭제 시 연결된 query_log의 is_converted_to_fewshot도 False로 변경
    if fewshot.source_query_log_id:
        from app.models.query_log import QueryLog
        query_log = session.get(QueryLog, fewshot.source_query_log_id)
        if query_log:
            query_log.is_converted_to_fewshot = False
            session.add(query_log)

    session.delete(fewshot)
    session.commit()
    return None


# ===== Few-shot Audit =====

@router.get("/audit/{fewshot_id}", response_model=List[FewShotAuditResponse])
async def get_fewshot_audit(
    fewshot_id: int,
    limit: int = Query(50, description="Maximum number of audit records", le=500),
    session: Session = Depends(get_session)
):
    """특정 Few-shot의 Audit 이력 조회."""
    statement = select(FewShotAudit).where(
        FewShotAudit.few_shot_id == fewshot_id
    ).order_by(FewShotAudit.created_at.desc()).limit(limit)

    audit_records = session.exec(statement).all()
    return audit_records


@router.get("/audit/", response_model=List[FewShotAuditResponse])
async def get_all_fewshot_audits(
    action: Optional[str] = Query(None, description="Filter by action (INSERT, UPDATE, DELETE)"),
    limit: int = Query(100, description="Maximum number of audit records", le=1000),
    session: Session = Depends(get_session)
):
    """모든 Few-shot Audit 이력 조회 (필터링 가능)."""
    statement = select(FewShotAudit)

    if action:
        statement = statement.where(FewShotAudit.action == action.upper())

    statement = statement.order_by(FewShotAudit.created_at.desc()).limit(limit)
    audit_records = session.exec(statement).all()
    return audit_records
