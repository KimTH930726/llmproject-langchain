"""
Qdrant 벡터 데이터베이스 연동 서비스
문서 임베딩 저장 및 검색 기능 제공
"""
import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from dotenv import load_dotenv

load_dotenv()

# 오프라인 모드 강제 (폐쇄망 환경에서 HuggingFace Hub 접속 차단)
# 반드시 TextEmbedding import 전에 설정되어야 함
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"


class QdrantService:
    """Qdrant 벡터 DB와 임베딩 모델을 관리하는 서비스"""

    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "documents")
        # FastEmbed 다국어 모델 (한국어 포함)
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

        # FastEmbed 캐시 경로 설정 (폐쇄망 환경)
        fastembed_cache = os.getenv("FASTEMBED_CACHE_PATH", "/app/fastembed_cache")

        # Qdrant 클라이언트 초기화
        self.client = QdrantClient(url=self.qdrant_url)

        # FastEmbed 임베딩 모델 로드 (경량, 다국어 지원)
        # 캐시 경로가 설정되어 있으면 해당 경로에서 모델 로드
        try:
            self.embedding_model = TextEmbedding(
                model_name=self.embedding_model_name,
                cache_dir=fastembed_cache
            )
            print(f"✅ FastEmbed 모델 로드 성공: {self.embedding_model_name}")
            print(f"   캐시 디렉토리: {fastembed_cache}")
        except Exception as e:
            print(f"❌ FastEmbed 모델 로드 실패: {e}")
            print(f"   캐시 디렉토리: {fastembed_cache}")
            print(f"   캐시 내용 확인:")
            if os.path.exists(fastembed_cache):
                import subprocess
                result = subprocess.run(["find", fastembed_cache, "-type", "f"],
                                      capture_output=True, text=True)
                print(result.stdout)
            raise

        self.vector_size = 768  # paraphrase-multilingual-mpnet-base-v2 벡터 크기

        # 컬렉션 생성 (없는 경우)
        self._ensure_collection()

    def _ensure_collection(self):
        """컬렉션이 없으면 생성"""
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any] = None) -> None:
        """
        문서를 벡터화하여 Qdrant에 저장

        Args:
            doc_id: 문서 고유 ID
            text: 문서 텍스트
            metadata: 추가 메타데이터 (파일명, 업로드 시간 등)
        """
        # 텍스트를 임베딩 벡터로 변환 (FastEmbed은 generator 반환)
        embeddings = list(self.embedding_model.embed([text]))
        vector = embeddings[0].tolist()

        # 메타데이터 기본값 설정
        payload = metadata or {}
        payload["text"] = text

        # Qdrant에 저장
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        쿼리와 유사한 문서 검색

        Args:
            query: 검색 쿼리
            limit: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트 (각 결과는 text, score, metadata 포함)
        """
        # 쿼리를 임베딩 벡터로 변환 (FastEmbed)
        embeddings = list(self.embedding_model.embed([query]))
        query_vector = embeddings[0].tolist()

        # Qdrant에서 유사 문서 검색
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )

        # 결과 포맷팅
        results = []
        for hit in search_result:
            results.append({
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"}
            })

        return results

    def delete_document(self, doc_id: str) -> None:
        """문서 삭제"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[doc_id]
        )

    def count_documents(self) -> int:
        """저장된 문서 개수 반환"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return collection_info.points_count or 0
        except Exception:
            # 에러 발생 시 0 반환 (컬렉션 없음 or 접근 불가)
            return 0

    def get_all_documents(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        저장된 모든 문서 조회 (페이징 지원)

        Args:
            limit: 반환할 최대 문서 수
            offset: 건너뛸 문서 수

        Returns:
            문서 리스트 (각 문서는 id, text, metadata 포함)
        """
        try:
            # Qdrant scroll API로 문서 조회
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False  # 벡터는 불필요 (용량 절약)
            )

            documents = []
            for point in scroll_result[0]:  # scroll_result는 (points, next_offset) 튜플
                doc = {
                    "id": str(point.id),
                    "text": point.payload.get("text", ""),
                    "metadata": {k: v for k, v in point.payload.items() if k != "text"}
                }
                documents.append(doc)

            return documents
        except Exception:
            # 에러 발생 시 빈 리스트 반환 (컬렉션 없음 or 접근 불가)
            return []

    def get_document_by_id(self, doc_id: str) -> Dict[str, Any]:
        """
        특정 문서 조회

        Args:
            doc_id: 문서 ID

        Returns:
            문서 정보 (id, text, metadata)
        """
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )

        if not points:
            return None

        point = points[0]
        return {
            "id": str(point.id),
            "text": point.payload.get("text", ""),
            "metadata": {k: v for k, v in point.payload.items() if k != "text"}
        }

    def get_collection_info(self) -> Dict[str, Any]:
        """
        컬렉션 정보 조회

        Returns:
            컬렉션 통계 정보
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)

            # Qdrant 버전에 따라 응답 구조가 다를 수 있으므로 안전하게 접근
            try:
                # 최신 버전 (config.params.vectors가 VectorParams 객체)
                vector_params = collection_info.config.params.vectors
                if hasattr(vector_params, 'size'):
                    vector_size = vector_params.size
                    distance = vector_params.distance.name if hasattr(vector_params.distance, 'name') else str(vector_params.distance)
                else:
                    # 딕셔너리 형태인 경우
                    vector_size = vector_params.get('size', self.vector_size)
                    distance = vector_params.get('distance', 'COSINE')
            except (AttributeError, TypeError):
                # fallback: 기본값 사용
                vector_size = self.vector_size
                distance = "COSINE"

            return {
                "name": self.collection_name,
                "points_count": collection_info.points_count or 0,
                "vector_size": vector_size,
                "distance": distance
            }
        except Exception as e:
            # 컬렉션 정보 조회 실패 시 기본 정보 반환
            return {
                "name": self.collection_name,
                "points_count": 0,
                "vector_size": self.vector_size,
                "distance": "COSINE",
                "error": str(e)
            }


# 싱글톤 인스턴스
qdrant_service = QdrantService()
