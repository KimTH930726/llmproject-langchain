import { useState } from 'react';
import IntentManagement from './components/IntentManagement';
import QueryLogManagement from './components/QueryLogManagement';
import FewShotManagement from './components/FewShotManagement';
import Dashboard from './components/Dashboard';
import './App.css';

type TabType = 'dashboard' | 'intent' | 'querylog' | 'fewshot';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
                <span className="text-2xl">💼</span>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  지원자 검색 시스템
                </h1>
                <p className="text-gray-600 text-sm mt-0.5">
                  AI 기반 의미검색으로 최적의 후보를 찾아보세요
                </p>
              </div>
            </div>
            <div className="text-sm text-gray-500">
              API: /api
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="flex gap-1 p-1 border-b border-gray-200">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex-1 px-4 py-3 font-medium text-sm rounded-lg transition-all duration-200 ${
                activeTab === 'dashboard'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              대시보드
            </button>
            <button
              onClick={() => setActiveTab('intent')}
              className={`flex-1 px-4 py-3 font-medium text-sm rounded-lg transition-all duration-200 ${
                activeTab === 'intent'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              Intent 관리
            </button>
            <button
              onClick={() => setActiveTab('fewshot')}
              className={`flex-1 px-4 py-3 font-medium text-sm rounded-lg transition-all duration-200 ${
                activeTab === 'fewshot'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              Few-shot 관리
            </button>
            <button
              onClick={() => setActiveTab('querylog')}
              className={`flex-1 px-4 py-3 font-medium text-sm rounded-lg transition-all duration-200 ${
                activeTab === 'querylog'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              질의 로그 관리
            </button>
          </div>

          {/* Content Area */}
          <div className="p-6">
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'intent' && <IntentManagement />}
            {activeTab === 'fewshot' && <FewShotManagement />}
            {activeTab === 'querylog' && <QueryLogManagement />}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-6 py-6 text-center">
        <p className="text-sm text-gray-500">
          52명 등록됨 · 총 <span className="font-semibold text-gray-700">50명</span> 표시
        </p>
      </footer>
    </div>
  );
}

export default App;
