import { useState, useEffect } from 'react';

interface Intent {
  id: number;
  keyword: string;
  intent_type: string;
  priority: number;
  description: string | null;
  created_at: string;
  updated_at: string;
}

interface IntentFormData {
  keyword: string;
  intent_type: string;
  priority: number;
  description: string;
}

// Nginx reverse proxy 사용 - 상대 경로로 호출 (폐쇄망 환경)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const INTENT_TYPES = [
  { value: 'rag_search', label: 'RAG 검색', icon: '🔍', color: 'bg-blue-100 text-blue-700' },
  { value: 'sql_query', label: 'SQL 쿼리', icon: '💾', color: 'bg-green-100 text-green-700' },
  { value: 'general', label: '일반 대화', icon: '💬', color: 'bg-gray-100 text-gray-700' },
];

export default function IntentManagement() {
  const [intents, setIntents] = useState<Intent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingIntent, setEditingIntent] = useState<Intent | null>(null);
  const [formData, setFormData] = useState<IntentFormData>({
    keyword: '',
    intent_type: 'rag_search',
    priority: 5,
    description: '',
  });

  const fetchIntents = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent/`);
      if (!response.ok) throw new Error('Failed to fetch intents');
      const data = await response.json();
      setIntents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntents();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create intent');
      }
      await fetchIntents();
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingIntent) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent/${editingIntent.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update intent');
      }
      await fetchIntents();
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('정말로 이 Intent를 삭제하시겠습니까?')) return;
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/intent/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete intent');
      await fetchIntents();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const startEdit = (intent: Intent) => {
    setEditingIntent(intent);
    setFormData({
      keyword: intent.keyword,
      intent_type: intent.intent_type,
      priority: intent.priority,
      description: intent.description || '',
    });
    setIsModalOpen(true);
  };

  const resetForm = () => {
    setFormData({ keyword: '', intent_type: 'rag_search', priority: 5, description: '' });
    setEditingIntent(null);
    setIsModalOpen(false);
  };

  const getIntentTypeInfo = (type: string) => {
    return INTENT_TYPES.find(t => t.value === type) || INTENT_TYPES[0];
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-6 rounded-xl shadow-lg">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold text-white">Intent 패턴 관리</h2>
            <p className="text-blue-100 mt-2">총 {intents.length}개의 패턴</p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-6 py-3 bg-white text-blue-700 rounded-xl hover:bg-blue-50 font-semibold shadow-md transition-all duration-200 hover:shadow-lg flex items-center gap-2"
          >
            <span className="text-xl">+</span> 새 패턴 추가
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded-lg shadow-sm">
          <p className="font-semibold">⚠ 오류가 발생했습니다</p>
          <p>{error}</p>
        </div>
      )}

      {/* Table */}
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
                <th className="px-6 py-4 text-left font-bold text-sm">키워드</th>
                <th className="px-6 py-4 text-left font-bold text-sm">Intent 타입</th>
                <th className="px-6 py-4 text-center font-bold text-sm">우선순위</th>
                <th className="px-6 py-4 text-left font-bold text-sm">설명</th>
                <th className="px-6 py-4 text-center font-bold text-sm">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-blue-100">
              {intents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    <div className="text-5xl mb-4">📋</div>
                    <p className="text-lg font-semibold">등록된 패턴이 없습니다</p>
                    <p className="text-sm text-gray-400 mt-2">첫 패턴을 추가해보세요</p>
                  </td>
                </tr>
              ) : (
                intents.map((intent) => {
                  const typeInfo = getIntentTypeInfo(intent.intent_type);
                  return (
                    <tr key={intent.id} className="hover:bg-blue-50 transition-colors duration-150">
                      <td className="px-6 py-4 text-gray-700 font-medium">{intent.id}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">{typeInfo.icon}</span>
                          <span className="font-bold text-blue-800">{intent.keyword}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1.5 rounded-full text-xs font-semibold ${typeInfo.color}`}>
                          {typeInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-800 font-bold">
                          {intent.priority}
                        </span>
                      </td>
                      <td className="px-6 py-4 max-w-md">
                        <div className="text-gray-600 line-clamp-2">{intent.description || '-'}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() => startEdit(intent)}
                            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 font-medium shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105"
                          >
                            수정
                          </button>
                          <button
                            onClick={() => handleDelete(intent.id)}
                            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 font-medium shadow-sm transition-all duration-200 hover:shadow-md hover:scale-105"
                          >
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 overflow-y-auto">
          <div className="min-h-screen flex items-start justify-center p-4 pt-12">
            <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-8 my-8">
            <form onSubmit={editingIntent ? handleUpdate : handleCreate}>
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b-2 border-blue-300 pb-3 mb-6">
                <h3 className="text-2xl font-bold text-blue-800">
                  {editingIntent ? '✏ Intent 수정' : '➕ Intent 추가'}
                </h3>
                <button
                  type="button"
                  onClick={resetForm}
                  className="text-gray-400 hover:text-gray-600 text-3xl leading-none w-8 h-8 flex items-center justify-center"
                >
                  ×
                </button>
              </div>

              {/* Modal Body */}
              <div className="space-y-4">
                {/* Keyword */}
                <div>
                  <label className="block text-sm font-semibold text-blue-900 mb-2">
                    키워드 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.keyword}
                    onChange={(e) => setFormData({ ...formData, keyword: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="예) 검색, 몇명, 안녕"
                    required
                  />
                </div>

                {/* Intent Type */}
                <div>
                  <label className="block text-sm font-semibold text-blue-900 mb-2">
                    의도 타입 <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.intent_type}
                    onChange={(e) => setFormData({ ...formData, intent_type: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    {INTENT_TYPES.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.icon} {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Priority */}
                <div>
                  <label className="block text-sm font-semibold text-blue-900 mb-2">
                    우선순위 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: Number(e.target.value) })}
                    className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="0-10 (높을수록 우선)"
                    min="0"
                    max="10"
                    required
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-semibold text-blue-900 mb-2">
                    설명
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="키워드에 대한 설명을 입력하세요"
                    rows={4}
                  />
                </div>
              </div>

              {/* Modal Footer */}
              <div className="flex gap-3 mt-6">
                <button
                  type="submit"
                  className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 font-semibold shadow-md transition-all duration-200 hover:shadow-lg"
                >
                  {editingIntent ? '수정하기' : '등록하기'}
                </button>
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 font-semibold shadow-md transition-all duration-200"
                >
                  취소
                </button>
              </div>
            </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
