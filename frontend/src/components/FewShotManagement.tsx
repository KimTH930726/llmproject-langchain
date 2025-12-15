import { useState, useEffect } from 'react';

interface FewShot {
  id: number;
  source_query_log_id: number | null;
  intent_type: string | null;
  user_query: string;
  expected_response: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface FewShotAudit {
  id: number;
  few_shot_id: number;
  action: string;
  old_value: any;
  new_value: any;
  changed_by: string | null;
  created_at: string;
}

// Nginx reverse proxy 사용 - 상대 경로로 호출 (폐쇄망 환경)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const INTENT_TYPES = [
  { value: '', label: '전체' },
  { value: 'rag_search', label: 'RAG 검색' },
  { value: 'sql_query', label: 'SQL 쿼리' },
  { value: 'general', label: '일반 대화' },
];

export default function FewShotManagement() {
  const [activeTab, setActiveTab] = useState<'fewshots' | 'audit'>('fewshots');
  const [fewShots, setFewShots] = useState<FewShot[]>([]);
  const [audits, setAudits] = useState<FewShotAudit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterIntentType, setFilterIntentType] = useState<string>('');
  const [filterActiveOnly, setFilterActiveOnly] = useState(false);
  const [selectedFewShotId, setSelectedFewShotId] = useState<number | null>(null);

  const fetchFewShots = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterIntentType) params.append('intent_type', filterIntentType);
      if (filterActiveOnly) params.append('is_active', 'true');

      const response = await fetch(`${API_BASE_URL}/api/fewshot/?${params}`);
      if (!response.ok) throw new Error('Failed to fetch few-shots');
      const data = await response.json();
      setFewShots(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchAudits = async (fewShotId?: number) => {
    setLoading(true);
    setError(null);
    try {
      const url = fewShotId
        ? `${API_BASE_URL}/api/fewshot/audit/${fewShotId}`
        : `${API_BASE_URL}/api/fewshot/audit/`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch audits');
      const data = await response.json();
      setAudits(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'fewshots') {
      fetchFewShots();
    } else if (activeTab === 'audit') {
      fetchAudits(selectedFewShotId || undefined);
    }
  }, [activeTab, filterIntentType, filterActiveOnly, selectedFewShotId]);

  const toggleActive = async (id: number, currentActive: boolean) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/fewshot/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !currentActive }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update few-shot');
      }
      await fetchFewShots();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말로 이 Few-shot을 삭제하시겠습니까?\n연결된 질의 로그의 변환 상태도 해제됩니다.')) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/fewshot/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete few-shot');
      await fetchFewShots();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const getIntentTypeBadge = (type: string | null) => {
    if (!type) return 'bg-gray-100 text-gray-800';
    const colors: Record<string, string> = {
      rag_search: 'bg-blue-100 text-blue-800',
      sql_query: 'bg-green-100 text-green-800',
      general: 'bg-purple-100 text-purple-800',
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  const getIntentTypeLabel = (type: string | null) => {
    if (!type) return '-';
    const labels: Record<string, string> = {
      rag_search: 'RAG 검색',
      sql_query: 'SQL 쿼리',
      general: '일반 대화',
    };
    return labels[type] || type;
  };

  return (
    <div className="space-y-8">
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-6 rounded-xl shadow-lg">
        <h2 className="text-3xl font-bold text-white">Few-shot 예제 관리</h2>
        <p className="text-blue-100 mt-2">프롬프트에 포함될 Few-shot 예제를 활성화/비활성화하세요</p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded-lg shadow-sm">
          <p className="font-semibold">⚠ 오류</p>
          <p>{error}</p>
        </div>
      )}

      {/* 탭 메뉴 */}
      <div className="flex gap-1 bg-blue-100 p-1 rounded-lg shadow-inner">
        <button
          onClick={() => setActiveTab('fewshots')}
          className={`flex-1 px-6 py-3 rounded-lg font-semibold transition-all duration-200 ${
            activeTab === 'fewshots'
              ? 'bg-white text-blue-700 shadow-md'
              : 'text-blue-600 hover:text-blue-800 hover:bg-blue-50'
          }`}
        >
          📚 Few-shot 예제
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`flex-1 px-6 py-3 rounded-lg font-semibold transition-all duration-200 ${
            activeTab === 'audit'
              ? 'bg-white text-blue-700 shadow-md'
              : 'text-blue-600 hover:text-blue-800 hover:bg-blue-50'
          }`}
        >
          📋 변경 이력
        </button>
      </div>

      {/* Few-shot 예제 탭 */}
      {activeTab === 'fewshots' && (
        <>
          <div className="flex justify-between items-center bg-blue-50 p-4 rounded-lg border border-blue-200">
            <div className="flex gap-4 items-center">
              <div>
                <label className="block text-sm font-semibold text-blue-900 mb-2">🔍 Intent 타입 필터</label>
                <select
                  value={filterIntentType}
                  onChange={(e) => setFilterIntentType(e.target.value)}
                  className="px-4 py-2 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  {INTENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-3 bg-white p-3 rounded-lg border-2 border-blue-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filterActiveOnly}
                    onChange={(e) => setFilterActiveOnly(e.target.checked)}
                    className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="text-sm font-semibold text-blue-900">✓ 활성화된 것만 보기</span>
                </label>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
              <p className="mt-4 text-blue-600 font-semibold">로딩 중...</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl shadow-lg border border-blue-200">
              <table className="min-w-full bg-white">
                <thead className="bg-gradient-to-r from-blue-600 to-blue-700 text-white">
                  <tr>
                    <th className="px-6 py-4 text-left font-bold text-sm">ID</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">원본 질의</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">Intent 타입</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">사용자 질의</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">예상 응답</th>
                    <th className="px-6 py-4 text-center font-bold text-sm">활성화</th>
                    <th className="px-6 py-4 text-center font-bold text-sm">작업</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-blue-100">
                  {fewShots.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                        <div className="text-5xl mb-4">📚</div>
                        <p className="text-lg font-semibold">등록된 Few-shot이 없습니다</p>
                        <p className="text-sm text-gray-400 mt-2">질의 로그 탭에서 질의를 Few-shot으로 승격하세요</p>
                      </td>
                    </tr>
                  ) : (
                    fewShots.map((fs) => (
                      <tr key={fs.id} className="hover:bg-blue-50 transition-colors duration-150">
                        <td className="px-6 py-4 text-gray-700 font-medium">{fs.id}</td>
                        <td className="px-6 py-4">
                          {fs.source_query_log_id ? (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">
                              🔗 #{fs.source_query_log_id}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1.5 rounded-full text-xs font-semibold ${getIntentTypeBadge(fs.intent_type)}`}>
                            {getIntentTypeLabel(fs.intent_type)}
                          </span>
                        </td>
                        <td className="px-6 py-4 max-w-md">
                          <div className="text-blue-800 font-medium line-clamp-2">{fs.user_query}</div>
                        </td>
                        <td className="px-6 py-4 max-w-md">
                          <div className="text-gray-600 line-clamp-2">{fs.expected_response || '-'}</div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => toggleActive(fs.id, fs.is_active)}
                            className={`inline-flex items-center px-4 py-2 rounded-lg font-semibold text-sm shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105 ${
                              fs.is_active
                                ? 'bg-green-500 text-white hover:bg-green-600'
                                : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
                            }`}
                          >
                            {fs.is_active ? '✓ 활성' : '✕ 비활성'}
                          </button>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-2 justify-center">
                            <button
                              onClick={() => handleDelete(fs.id)}
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
        </>
      )}

      {/* 변경 이력 탭 */}
      {activeTab === 'audit' && (
        <>
          <div className="flex gap-3 items-center bg-blue-50 p-4 rounded-lg border border-blue-200">
            <label className="text-sm font-semibold text-blue-900">🔍 Few-shot ID 필터:</label>
            <input
              type="number"
              value={selectedFewShotId || ''}
              onChange={(e) => setSelectedFewShotId(e.target.value ? Number(e.target.value) : null)}
              placeholder="전체"
              className="px-4 py-2 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-40 bg-white"
            />
          </div>
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
              <p className="mt-4 text-blue-600 font-semibold">로딩 중...</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl shadow-lg border border-blue-200">
              <table className="min-w-full bg-white">
                <thead className="bg-gradient-to-r from-blue-600 to-blue-700 text-white">
                  <tr>
                    <th className="px-6 py-4 text-left font-bold text-sm">ID</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">Few-shot ID</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">작업</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">변경자</th>
                    <th className="px-6 py-4 text-left font-bold text-sm">생성일</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-blue-100">
                  {audits.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                        <div className="text-5xl mb-4">📋</div>
                        <p className="text-lg font-semibold">변경 이력이 없습니다</p>
                      </td>
                    </tr>
                  ) : (
                    audits.map((audit) => (
                      <tr key={audit.id} className="hover:bg-blue-50 transition-colors duration-150">
                        <td className="px-6 py-4 text-gray-700 font-medium">{audit.id}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-800 font-bold">
                            {audit.few_shot_id}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold ${
                              audit.action === 'INSERT'
                                ? 'bg-green-100 text-green-800'
                                : audit.action === 'UPDATE'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {audit.action === 'INSERT' ? '➕ INSERT' : audit.action === 'UPDATE' ? '✏ UPDATE' : '🗑 DELETE'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-600">{audit.changed_by || '-'}</td>
                        <td className="px-6 py-4 text-gray-600 text-sm">
                          {new Date(audit.created_at).toLocaleString('ko-KR')}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
