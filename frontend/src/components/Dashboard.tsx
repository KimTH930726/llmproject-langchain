import { useState, useEffect } from 'react';

interface CollectionInfo {
  name: string;
  points_count: number;
  vector_size: number;
  distance: string;
}

interface Document {
  id: string;
  text: string;
  metadata: {
    filename?: string;
    upload_time?: string;
    file_size?: number;
  };
}

interface DocumentsResponse {
  total: number;
  limit: number;
  offset: number;
  documents: Document[];
}

// Nginx reverse proxy 사용 - 상대 경로로 호출 (폐쇄망 환경)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function Dashboard() {
  const [collectionInfo, setCollectionInfo] = useState<CollectionInfo | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    fetchCollectionInfo();
    fetchDocuments();
  }, []);

  const fetchCollectionInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/upload/stats`);
      if (!response.ok) throw new Error('Failed to fetch collection info');
      const data = await response.json();
      setCollectionInfo(data);
    } catch (err) {
      console.error('Collection info fetch error:', err);
    }
  };

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/upload/documents?limit=100`);
      if (!response.ok) throw new Error('Failed to fetch documents');
      const data: DocumentsResponse = await response.json();
      setDocuments(data.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('정말로 이 문서를 삭제하시겠습니까?')) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/upload/documents/${docId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete document');
      await fetchDocuments();
      await fetchCollectionInfo();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const openDetailModal = (doc: Document) => {
    setSelectedDoc(doc);
    setShowDetailModal(true);
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('ko-KR');
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-purple-700 p-6 rounded-xl shadow-lg">
        <h2 className="text-3xl font-bold text-white">시스템 대시보드</h2>
        <p className="text-purple-100 mt-2">벡터 DB 및 문서 관리</p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded-lg shadow-sm">
          <p className="font-semibold">⚠ 오류</p>
          <p>{error}</p>
        </div>
      )}

      {/* 통계 카드 */}
      {collectionInfo && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-purple-200">
            <div className="text-sm font-semibold text-purple-600">컬렉션명</div>
            <div className="text-2xl font-bold text-purple-800 mt-2">{collectionInfo.name}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-blue-200">
            <div className="text-sm font-semibold text-blue-600">총 문서 수</div>
            <div className="text-3xl font-bold text-blue-800 mt-2">{collectionInfo.points_count}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-green-200">
            <div className="text-sm font-semibold text-green-600">벡터 차원</div>
            <div className="text-3xl font-bold text-green-800 mt-2">{collectionInfo.vector_size}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-indigo-200">
            <div className="text-sm font-semibold text-indigo-600">유사도 측정</div>
            <div className="text-2xl font-bold text-indigo-800 mt-2">{collectionInfo.distance}</div>
          </div>
        </div>
      )}

      {/* 문서 목록 */}
      <div className="bg-white rounded-xl shadow-lg border border-purple-200 overflow-hidden">
        <div className="bg-gradient-to-r from-purple-600 to-purple-700 p-4">
          <h3 className="text-xl font-bold text-white">저장된 문서 목록</h3>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-purple-600 border-t-transparent"></div>
            <p className="mt-4 text-purple-600 font-semibold">로딩 중...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-purple-50">
                <tr>
                  <th className="px-6 py-4 text-left font-bold text-sm text-purple-900">파일명</th>
                  <th className="px-6 py-4 text-left font-bold text-sm text-purple-900">문서 ID</th>
                  <th className="px-6 py-4 text-left font-bold text-sm text-purple-900">텍스트 미리보기</th>
                  <th className="px-6 py-4 text-center font-bold text-sm text-purple-900">파일 크기</th>
                  <th className="px-6 py-4 text-center font-bold text-sm text-purple-900">업로드 시간</th>
                  <th className="px-6 py-4 text-center font-bold text-sm text-purple-900">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-purple-100">
                {documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                      <div className="text-5xl mb-4">📄</div>
                      <p className="text-lg font-semibold">저장된 문서가 없습니다</p>
                      <p className="text-sm text-gray-400 mt-2">문서를 업로드하여 RAG 검색을 시작하세요</p>
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-purple-50 transition-colors duration-150">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">📄</span>
                          <span className="font-semibold text-purple-800">
                            {doc.metadata.filename || 'Unknown'}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-700">
                          {doc.id.substring(0, 12)}...
                        </code>
                      </td>
                      <td className="px-6 py-4 max-w-md">
                        <div className="text-gray-600 line-clamp-2 text-sm">{doc.text}</div>
                      </td>
                      <td className="px-6 py-4 text-center text-gray-600 text-sm">
                        {formatFileSize(doc.metadata.file_size)}
                      </td>
                      <td className="px-6 py-4 text-center text-gray-600 text-sm">
                        {formatDate(doc.metadata.upload_time)}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() => openDetailModal(doc)}
                            className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 font-medium shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105"
                          >
                            상세
                          </button>
                          <button
                            onClick={() => handleDelete(doc.id)}
                            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 font-medium shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105"
                          >
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 문서 상세 모달 */}
      {showDetailModal && selectedDoc && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-8">
            <div className="flex items-center justify-between border-b-2 border-purple-300 pb-3 mb-6">
              <h3 className="text-2xl font-bold text-purple-800">📄 문서 상세 정보</h3>
              <button
                onClick={() => setShowDetailModal(false)}
                className="text-gray-400 hover:text-gray-600 text-3xl leading-none w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-purple-900 mb-2">파일명</label>
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-200 text-purple-800 font-medium">
                  {selectedDoc.metadata.filename || 'Unknown'}
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-purple-900 mb-2">문서 ID</label>
                <code className="block p-4 bg-gray-50 rounded-lg border border-gray-200 text-gray-700 text-sm break-all">
                  {selectedDoc.id}
                </code>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-purple-900 mb-2">파일 크기</label>
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 text-blue-800">
                    {formatFileSize(selectedDoc.metadata.file_size)}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-purple-900 mb-2">업로드 시간</label>
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200 text-green-800">
                    {formatDate(selectedDoc.metadata.upload_time)}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-purple-900 mb-2">
                  전체 텍스트 ({selectedDoc.text.length.toLocaleString()} 자)
                </label>
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 max-h-96 overflow-y-auto">
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                    {selectedDoc.text}
                  </pre>
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowDetailModal(false)}
                className="flex-1 px-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 font-semibold shadow-md transition-all duration-200"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
