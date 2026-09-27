import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, 
  Bot, 
  Radio, 
  AlertTriangle, 
  ArrowRight, 
  PlusCircle, 
  Loader2, 
  Search, 
  RefreshCw 
} from 'lucide-react';
import { api } from '../api/client';

export default function AnalystDashboard({ onSelectConversation }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [startingSim, setStartingSim] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all', 'sms', 'simulated', 'pending'
  const [searchQuery, setSearchQuery] = useState('');

  const fetchConversations = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.listConversations();
      setConversations(data);
    } catch (err) {
      setError(err.message || 'Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
    const interval = setInterval(fetchConversations, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleStartSimulation = async () => {
    setStartingSim(true);
    try {
      const res = await api.startSimulatedConversation();
      await fetchConversations();
      if (res.conversation_id && onSelectConversation) {
        onSelectConversation(res.conversation_id);
      }
    } catch (err) {
      alert(`Failed to start simulated conversation: ${err.message}`);
    } finally {
      setStartingSim(false);
    }
  };

  const filteredConversations = conversations.filter((c) => {
    if (filter === 'sms' && c.channel !== 'sms') return false;
    if (filter === 'simulated' && c.channel !== 'simulated') return false;
    if (filter === 'pending' && !c.has_pending_review) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        c.scammer_contact.toLowerCase().includes(q) ||
        (c.last_message && c.last_message.toLowerCase().includes(q)) ||
        c.persona_name.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">Analyst Operations Dashboard</h1>
          <p className="text-sm text-slate mt-0.5">
            Monitor incoming scammer channels, review flagged turns, and inspect threat indicators.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchConversations}
            disabled={loading}
            className="p-2 border border-lineBorder rounded-lg text-slate hover:bg-gray-100 transition"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={handleStartSimulation}
            disabled={startingSim}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-hover active:scale-95 transition shadow-sm disabled:opacity-50"
          >
            {startingSim ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Seeding Decoy...
              </>
            ) : (
              <>
                <PlusCircle className="w-4 h-4" />
                Start Demo Simulation
              </>
            )}
          </button>
        </div>
      </div>

      {/* Filter Chips & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-4 rounded-xl border border-lineBorder shadow-sm">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
          {[
            { id: 'all', label: 'All Operations', count: conversations.length },
            { id: 'sms', label: 'Real SMS', count: conversations.filter((c) => c.channel === 'sms').length },
            { id: 'simulated', label: 'Simulated Bot', count: conversations.filter((c) => c.channel === 'simulated').length },
            { id: 'pending', label: 'Needs Review', count: conversations.filter((c) => c.has_pending_review).length },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition flex items-center gap-1.5 ${
                filter === tab.id
                  ? 'bg-ink text-white'
                  : 'bg-gray-100 text-slate hover:bg-gray-200'
              }`}
            >
              <span>{tab.label}</span>
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${filter === tab.id ? 'bg-white/20 text-white' : 'bg-white text-slate'}`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative w-full md:w-64">
          <Search className="w-4 h-4 text-slate absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search contact, text, persona..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-gray-50 border border-lineBorder rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:bg-white transition"
          />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-danger rounded-xl text-xs font-medium flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={fetchConversations}
            className="ml-3 px-3 py-1 bg-white border border-red-300 rounded-lg text-xs font-semibold text-danger hover:bg-red-100 flex items-center gap-1.5 transition shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      )}

      {/* Conversation List Table */}
      <div className="bg-surface border border-lineBorder rounded-xl overflow-hidden shadow-sm">
        {loading && conversations.length === 0 ? (
          <div className="p-12 text-center text-slate flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm">Loading active decoy operations...</p>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="p-12 text-center text-slate flex flex-col items-center gap-3">
            <MessageSquare className="w-10 h-10 text-gray-300" />
            <p className="text-sm font-medium text-ink">No conversations found</p>
            <p className="text-xs text-slate">
              {searchQuery
                ? 'Try adjusting your search criteria.'
                : 'Click "Start Demo Simulation" or send an SMS to your Twilio number to begin.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-lineBorder">
            {filteredConversations.map((conv) => {
              const isSimulated = conv.channel === 'simulated';
              const risk = conv.risk_score;

              let riskBadge = null;
              if (risk !== null && risk !== undefined) {
                if (risk >= 70) {
                  riskBadge = (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-danger border border-red-200">
                      Score: {risk} (High)
                    </span>
                  );
                } else if (risk >= 30) {
                  riskBadge = (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-warning border border-amber-200">
                      Score: {risk} (Suspicious)
                    </span>
                  );
                } else {
                  riskBadge = (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-success border border-green-200">
                      Score: {risk} (Low)
                    </span>
                  );
                }
              }

              return (
                <div
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className="p-4 hover:bg-gray-50/80 transition cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group"
                >
                  {/* Left: Channel Badge, Contact, Snippet */}
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="mt-1">
                      {isSimulated ? (
                        <div className="w-9 h-9 rounded-xl bg-info/10 text-info flex items-center justify-center border border-info/30" title="Simulated Honeypot">
                          <Bot className="w-5 h-5" />
                        </div>
                      ) : (
                        <div className="w-9 h-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/30" title="Live SMS">
                          <Radio className="w-5 h-5" />
                        </div>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-semibold text-sm text-ink">{conv.scammer_contact}</span>

                        {/* Visual Distinction: Info color for simulated per spec §1 */}
                        {isSimulated ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-info/15 text-info border border-info/30 uppercase tracking-wider">
                            Simulated Bot
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-primary/10 text-primary border border-primary/20 uppercase tracking-wider">
                            Live Twilio SMS
                          </span>
                        )}

                        <span className="text-xs text-slate">
                          Decoy: <span className="font-medium text-ink">{conv.persona_name}</span>
                        </span>

                        {conv.has_pending_review && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-warning border border-warning/40 animate-pulse">
                            <AlertTriangle className="w-3 h-3" />
                            Review Required
                          </span>
                        )}

                        {conv.status === 'halted' && (
                          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-200 text-slate">
                            Halted
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate line-clamp-1">
                        {conv.last_message ? (
                          <span>Latest: &ldquo;{conv.last_message}&rdquo;</span>
                        ) : (
                          <span className="italic">No messages yet</span>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Right: Message Count, Risk Badge, Navigation */}
                  <div className="flex items-center gap-4 self-end md:self-center shrink-0">
                    <div className="text-right">
                      <div className="text-xs text-slate font-medium">
                        {conv.message_count} {conv.message_count === 1 ? 'turn' : 'turns'}
                      </div>
                      <div className="mt-1">{riskBadge}</div>
                    </div>

                    <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center text-slate group-hover:bg-primary group-hover:text-white transition">
                      <ArrowRight className="w-4 h-4" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
