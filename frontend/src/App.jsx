import React, { useState } from 'react';
import { 
  ShieldCheck, 
  MessageSquare, 
  Inbox, 
  Building2, 
  Key, 
  Layers 
} from 'lucide-react';
import AnalystDashboard from './pages/AnalystDashboard';
import ConversationView from './pages/ConversationView';
import ReviewQueue from './pages/ReviewQueue';
import InstitutionDashboard from './pages/InstitutionDashboard';
import { getApiKey, setApiKey } from './api/client';

export default function App() {
  const [currentTab, setCurrentTab] = useState('analyst'); // 'analyst', 'review', 'institution'
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [apiKey, setLocalApiKey] = useState(getApiKey());
  const [showKeyModal, setShowKeyModal] = useState(false);

  const handleSaveKey = (e) => {
    e.preventDefault();
    setApiKey(apiKey);
    setShowKeyModal(false);
  };

  const navigateToConversation = (id) => {
    setSelectedConversationId(id);
    setCurrentTab('analyst');
  };

  return (
    <div className="flex min-h-screen bg-pageBg text-ink font-sans">
      {/* Fixed Left Sidebar (240px width per Frontend Spec §1) */}
      <aside className="w-[240px] bg-white border-r border-lineBorder flex flex-col shrink-0 fixed inset-y-0 left-0 z-30">
        {/* Brand Header */}
        <div className="p-5 border-b border-lineBorder flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-white shadow-sm shadow-primary/30">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-base text-ink tracking-tight">TrapLine</h1>
            <p className="text-[11px] font-medium text-slate uppercase tracking-wider">Fraud Intelligence</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="p-3 space-y-1 flex-1">
          <button
            onClick={() => {
              setSelectedConversationId(null);
              setCurrentTab('analyst');
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition ${
              currentTab === 'analyst' && !selectedConversationId
                ? 'bg-primary text-white shadow-sm'
                : 'text-slate hover:bg-gray-100 hover:text-ink'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Analyst Dashboard</span>
          </button>

          <button
            onClick={() => {
              setSelectedConversationId(null);
              setCurrentTab('review');
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition ${
              currentTab === 'review'
                ? 'bg-primary text-white shadow-sm'
                : 'text-slate hover:bg-gray-100 hover:text-ink'
            }`}
          >
            <Inbox className="w-4 h-4" />
            <span>Review Queue</span>
          </button>

          <button
            onClick={() => {
              setSelectedConversationId(null);
              setCurrentTab('institution');
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition ${
              currentTab === 'institution'
                ? 'bg-primary text-white shadow-sm'
                : 'text-slate hover:bg-gray-100 hover:text-ink'
            }`}
          >
            <Building2 className="w-4 h-4" />
            <span>Institution View</span>
          </button>
        </nav>

        {/* Bottom System & Auth Pill */}
        <div className="p-3 border-t border-lineBorder space-y-2">
          <button
            onClick={() => setShowKeyModal(true)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs text-slate hover:bg-gray-100 border border-lineBorder transition"
          >
            <span className="flex items-center gap-2">
              <Key className="w-3.5 h-3.5 text-primary" />
              API Key Auth
            </span>
            <span className="text-[10px] bg-green-100 text-success font-bold px-1.5 py-0.5 rounded">Active</span>
          </button>

          <div className="px-3 py-1.5 text-[11px] text-slate/70 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-success"></span>
            Backend: Online (Port 8000)
          </div>
        </div>
      </aside>

      {/* Main Content Area (offset by 240px sidebar, 24px padding, 1200px max width) */}
      <main className="ml-[240px] flex-1 p-6 min-h-screen">
        <div className="max-w-[1200px] mx-auto">
          {selectedConversationId ? (
            <ConversationView
              conversationId={selectedConversationId}
              onBack={() => setSelectedConversationId(null)}
            />
          ) : currentTab === 'analyst' ? (
            <AnalystDashboard onSelectConversation={navigateToConversation} />
          ) : currentTab === 'review' ? (
            <ReviewQueue onSelectConversation={navigateToConversation} />
          ) : (
            <InstitutionDashboard />
          )}
        </div>
      </main>

      {/* API Key Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-lineBorder">
            <h3 className="text-base font-bold text-ink mb-1">API Key & Role Settings</h3>
            <p className="text-xs text-slate mb-3">
              Select a preset role or enter a custom key matching your backend configuration.
            </p>
            <div className="flex gap-2 mb-4">
              <button
                type="button"
                onClick={() => setLocalApiKey('trapline_admin_secret_key')}
                className="text-[11px] px-2.5 py-1 rounded-md border border-lineBorder bg-slate-50 hover:bg-slate-100 font-medium text-ink transition"
              >
                Admin Key
              </button>
              <button
                type="button"
                onClick={() => setLocalApiKey('trapline_analyst_secret_key')}
                className="text-[11px] px-2.5 py-1 rounded-md border border-lineBorder bg-slate-50 hover:bg-slate-100 font-medium text-ink transition"
              >
                Analyst Key
              </button>
              <button
                type="button"
                onClick={() => setLocalApiKey('trapline_institution_secret_key')}
                className="text-[11px] px-2.5 py-1 rounded-md border border-lineBorder bg-slate-50 hover:bg-slate-100 font-medium text-ink transition"
              >
                Institution Key
              </button>
            </div>
            <form onSubmit={handleSaveKey} className="space-y-4">
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setLocalApiKey(e.target.value)}
                placeholder="Enter API Key..."
                className="w-full text-xs font-mono p-3 border border-lineBorder rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="px-4 py-2 border border-lineBorder rounded-lg text-xs font-semibold text-slate hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-primary text-white rounded-lg text-xs font-semibold hover:bg-primary-hover shadow-sm"
                >
                  Save API Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
