import { useState, useEffect } from 'react';

interface QueryLog {
  id: number;
  query_text: string;
  detected_intent: string | null;
  response: string | null;
  is_converted_to_fewshot: boolean;
  created_at: string;
}

interface QueryLogStats {
  total_queries: number;
  converted_to_fewshot: number;
  conversion_rate: number;
  by_intent: Array<{ intent: string; count: number }>;
}

// Nginx reverse proxy 사용 - 상대 경로로 호출 (폐쇄망 환경)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const INTENT_TYPES = [
  { value: '', label: '전체' },
  { value: 'rag_search', label: 'RAG 검색' },
  { value: 'sql_query', label: 'SQL 쿼리' },
  { value: 'general', label: '일반 대화' },
];

export default function QueryLogManagement() {
  const [queryLogs, setQueryLogs] = useState<QueryLog[]>([]);
  const [stats, setStats] = useState<QueryLogStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterIntent, setFilterIntent] = useState<string>('');
  const [convertedOnly, setConvertedOnly] = useState(false);
  const [searchText, setSearchText] = useState('');

  const fetchQueryLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterIntent) params.append('intent', filterIntent);
      if (convertedOnly) params.append('converted_only', 'true');
      if (searchText) params.append('search', searchText);
      params.append('limit', '100');

      const response = await fetch(`${API_BASE_URL}/api/query-logs/?${params}`);
      if (!response.ok) throw new Error('Failed to fetch query logs');
      const data = await response.json();
      setQueryLogs(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/query-logs/stats/summary`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Stats fetch error:', err);
    }
  };

  useEffect(() => {
    fetchQueryLogs();
    fetchStats();
  }, [filterIntent, convertedOnly]);

  const handleSearch = () => {
    fetchQueryLogs();
  };

  const handleConvertToFewShot = async (log: QueryLog) => {
    if (!confirm(`질의 로그를 Few-shot 예제로 승격하시겠습니까?\n\n질의: ${log.query_text}`)) {
      return;
    }

    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/query-logs/convert-to-fewshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_log_id: log.id,
          intent_type: log.detected_intent || '',
          expected_response: log.response || '',
          is_active: true,
        }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to convert to few-shot');
      }
      alert('Few-shot 예제로 승격되었습니다.');
      await fetchQueryLogs();
      await fetchStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말로 이 질의 로그를 삭제하시겠습니까?')) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/query-logs/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete query log');
      }
      await fetchQueryLogs();
      await fetchStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const getIntentBadgeColor = (intent: string | null) => {
    if (!intent) return 'bg-gray-100 text-gray-800';
    const colors: Record<string, string> = {
      rag_search: 'bg-blue-100 text-blue-800',
      sql_query: 'bg-green-100 text-green-800',
      general: 'bg-purple-100 text-purple-800',
    };
    return colors[intent] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="space-y-8">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-6 rounded-xl shadow-lg">
        <h2 className="text-3xl font-bold text-white">질의 로그 관리</h2>
        <p className="text-blue-100 mt-2">사용자 질의 내역을 확인하고 Few-shot 예제로 승격하세요</p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded-lg shadow-sm">
          <p className="font-semibold">⚠ 오류</p>
          <p>{error}</p>
        </div>
      )}

      {/* 통계 */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-blue-200">
            <div className="text-sm font-semibold text-blue-600">전체 질의</div>
            <div className="text-3xl font-bold text-blue-800 mt-2">{stats.total_queries}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-green-200">
            <div className="text-sm font-semibold text-green-600">Few-shot 변환</div>
            <div className="text-3xl font-bold text-green-800 mt-2">{stats.converted_to_fewshot}</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-purple-200">
            <div className="text-sm font-semibold text-purple-600">변환율</div>
            <div className="text-3xl font-bold text-purple-800 mt-2">{stats.conversion_rate}%</div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-lg border-2 border-indigo-200">
            <div className="text-sm font-semibold text-indigo-600">의도 타입</div>
            <div className="text-sm text-indigo-800 mt-2 space-y-1">
              {stats.by_intent.map((item) => (
                <div key={item.intent} className="flex justify-between">
                  <span>{item.intent}</span>
                  <span className="font-bold">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 필터 */}
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-semibold text-blue-900 mb-2">🔍 Intent 필터</label>
            <select
              value={filterIntent}
              onChange={(e) => setFilterIntent(e.target.value)}
              className="w-full px-4 py-2 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {INTENT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-blue-900 mb-2">📝 질의 검색</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="질의 텍스트 검색..."
                className="flex-1 px-4 py-2 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              />
              <button
                onClick={handleSearch}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow-md transition-all duration-200 hover:shadow-lg"
              >
                검색
              </button>
            </div>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-3 bg-white p-4 rounded-lg border-2 border-blue-200 cursor-pointer">
              <input
                type="checkbox"
                checked={convertedOnly}
                onChange={(e) => setConvertedOnly(e.target.checked)}
                className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm font-semibold text-blue-900">✅ 변환된 것만 보기</span>
            </label>
          </div>
        </div>
      </div>

      {/* 질의 로그 테이블 */}
      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
          <p className="mt-4 text-blue-600 font-semibold">로딩 중...</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl shadow-lg border border-blue-200">
          <table className="min-w-full bg-white">
            <thead className="bg-gradient-to-r from-blue-600 to-blue-700 text-white">
              <tr>
                <th className="px-4 py-4 text-left font-bold text-sm" style={{width: '60px'}}>ID</th>
                <th className="px-4 py-4 text-left font-bold text-sm" style={{minWidth: '500px'}}>질의 텍스트</th>
                <th className="px-4 py-4 text-left font-bold text-sm" style={{width: '100px'}}>의도</th>
                <th className="px-4 py-4 text-center font-bold text-sm" style={{width: '120px'}}>Few-shot 변환</th>
                <th className="px-4 py-4 text-left font-bold text-sm" style={{width: '180px'}}>생성일</th>
                <th className="px-4 py-4 text-center font-bold text-sm" style={{width: '180px'}}>작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-blue-100">
              {queryLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    <div className="text-5xl mb-4">💬</div>
                    <p className="text-lg font-semibold">질의 로그가 없습니다</p>
                  </td>
                </tr>
              ) : (
                queryLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-blue-50 transition-colors duration-150">
                    <td className="px-4 py-4 text-gray-700 font-medium text-sm">{log.id}</td>
                    <td className="px-4 py-4">
                      <div className="text-blue-800 font-medium text-sm break-words">{log.query_text}</div>
                      {log.response && (
                        <div className="text-xs text-gray-500 mt-1 break-words line-clamp-2">
                          응답: {log.response}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${getIntentBadgeColor(log.detected_intent)}`}>
                        {log.detected_intent || '미분류'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {log.is_converted_to_fewshot ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800 whitespace-nowrap">
                          ✓ 변환됨
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-gray-200 text-gray-600 whitespace-nowrap">
                          ○ 미변환
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-gray-600 text-xs whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('ko-KR')}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex gap-2 justify-center">
                        <button
                          onClick={() => handleConvertToFewShot(log)}
                          disabled={log.is_converted_to_fewshot}
                          className={`px-3 py-1.5 rounded-lg font-medium shadow-sm transition-all duration-200 text-xs whitespace-nowrap ${
                            log.is_converted_to_fewshot
                              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                              : 'bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 hover:shadow-md hover:scale-105'
                          }`}
                        >
                          ⬆ 승격
                        </button>
                        <button
                          onClick={() => handleDelete(log.id)}
                          className="px-3 py-1.5 bg-red-500 text-white rounded-lg hover:bg-red-600 font-medium shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105 text-xs whitespace-nowrap"
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
  );
}
