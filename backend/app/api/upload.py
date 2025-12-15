"""
파일 업로드 API
문서를 업로드하여 Qdrant 벡터 DB에 저장
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime
import hashlib

from app.models.chat import UploadResponse
from app.services.qdrant_service import qdrant_service
from app.utils.text_extractor import TextExtractor

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    문서 파일을 업로드하여 벡터 DB에 저장

    지원 형식: PDF, DOCX, TXT, XLSX

    - file: 업로드할 파일
    """
    try:
        # 1. 파일에서 텍스트 추출
        file_content = await file.read()
        text = TextExtractor.extract_text(file_content, file.filename)

        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="추출된 텍스트가 너무 짧습니다")

        # 2. 문서 ID 생성 (파일명 + 타임스탬프 해시)
        doc_id_raw = f"{file.filename}_{datetime.now().isoformat()}"
        doc_id = hashlib.md5(doc_id_raw.encode()).hexdigest()

        # 3. 메타데이터 구성
        metadata = {
            "filename": file.filename,
            "upload_time": datetime.now().isoformat(),
            "file_size": len(file_content),
        }

        # 4. Qdrant에 저장
        qdrant_service.add_document(
            doc_id=doc_id,
            text=text,
            metadata=metadata
        )

        return UploadResponse(
            message="파일이 성공적으로 업로드되었습니다",
            filename=file.filename,
            doc_id=doc_id,
            text_length=len(text)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")


@router.get("/stats")
async def get_upload_stats():
    """업로드된 문서 통계 및 컬렉션 정보"""
    try:
        collection_info = qdrant_service.get_collection_info()
        return collection_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/documents")
async def get_documents(
    limit: int = 100,
    offset: int = 0
):
    """
    저장된 문서 목록 조회

    - limit: 반환할 최대 문서 수 (기본 100)
    - offset: 건너뛸 문서 수 (페이징용)
    """
    try:
        documents = qdrant_service.get_all_documents(limit=limit, offset=offset)
        total = qdrant_service.count_documents()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 조회 실패: {str(e)}")


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """특정 문서 상세 조회"""
    try:
        document = qdrant_service.get_document_by_id(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
        return document
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 조회 실패: {str(e)}")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """문서 삭제"""
    try:
        # 문서 존재 확인
        document = qdrant_service.get_document_by_id(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")

        # 삭제
        qdrant_service.delete_document(doc_id)
        return {
            "message": "문서가 성공적으로 삭제되었습니다",
            "doc_id": doc_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 삭제 실패: {str(e)}")
