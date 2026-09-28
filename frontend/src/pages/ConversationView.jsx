import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  Bot, 
  Radio, 
  Play, 
  Loader2, 
  RefreshCw, 
  AlertTriangle, 
  UserCheck, 
  ShieldCheck, 
  Sparkles 
} from 'lucide-react';
import { api } from '../api/client';
import ConversationBubble from '../components/ConversationBubble';
import RiskScoreGauge from '../components/RiskScoreGauge';
import IndicatorTable from '../components/IndicatorTable';
import ReviewModal from '../components/ReviewModal';

export default function ConversationView({ conversationId, onBack }) {
  const [conversation, setConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [error, setError] = useState('');
  const [selectedMessageForReview, setSelectedMessageForReview] = useState(null);
  const transcriptEndRef = useRef(null);

  const fetchDetail = async () => {
    try {
      const data = await api.getConversation(conversationId);
      setConversation(data);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load conversation details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
    const interval = setInterval(fetchDetail, 5000);
    return () => clearInterval(interval);
  }, [conversationId]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages]);

  const handleAdvanceSimulation = async () => {
    setAdvancing(true);
    try {
      await api.nextSimulatedTurn(conversationId);
      await fetchDetail();
      setTimeout(() => {
        fetchDetail();
      }, 2000);
    } catch (err) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setAdvancing(false);
    }
  };

  const handleExplain = async () => {
    setExplaining(true);
    try {
      const res = await api.explainRisk(conversationId);
      setConversation((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          risk_assessment: prev.risk_assessment
            ? { ...prev.risk_assessment, explanation: res.explanation }
            : { explanation: res.explanation, risk_score: 0, classification: 'UNKNOWN', reasons: [] }
        };
      });
    } catch (err) {
      alert(`Narrative briefing error: ${err.message}`);
    } finally {
      setExplaining(false);
    }
  };

  if (loading && !conversation) {
    return (
      <div className="p-16 text-center text-slate flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-medium">Loading conversation transcript & threat intelligence...</p>
      </div>
    );
  }

  if (error && !conversation) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="p-4 bg-red-50 border border-red-200 text-danger rounded-xl text-sm font-medium">
          {error}
        </div>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-4 py-2 border border-lineBorder rounded-lg text-sm text-ink hover:bg-gray-100"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Operations
        </button>
      </div>
    );
  }

  const isSimulated = conversation.channel === 'simulated';
  const pendingMessage = conversation.messages.find((m) => m.review_status === 'pending');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Bar with Navigation & Meta */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-4 rounded-xl border border-lineBorder shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg border border-lineBorder text-slate hover:bg-gray-100 hover:text-ink transition"
            title="Back to dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-ink tracking-tight">{conversation.scammer_contact}</h2>
              {isSimulated ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-info/15 text-info border border-info/30 uppercase tracking-wider">
                  <Bot className="w-3 h-3" /> Simulated
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-primary/10 text-primary border border-primary/20 uppercase tracking-wider">
                  <Radio className="w-3 h-3" /> Live SMS
                </span>
              )}

              {conversation.status === 'halted' && (
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-100 text-danger">
                  HALTED
                </span>
              )}
            </div>

            <p className="text-xs text-slate mt-0.5">
              Decoy Identity: <span className="font-semibold text-ink">{conversation.persona_name}</span> •{' '}
              {conversation.messages.length} total turns
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDetail}
            className="p-2 border border-lineBorder rounded-lg text-slate hover:bg-gray-100 transition"
            title="Refresh now"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {isSimulated && conversation.status !== 'halted' && (
            <button
              onClick={handleAdvanceSimulation}
              disabled={advancing || !!pendingMessage}
              className="inline-flex items-center gap-2 px-4 py-2 bg-ink text-white rounded-lg text-xs font-semibold hover:bg-black active:scale-95 transition shadow-sm disabled:opacity-50"
              title={pendingMessage ? 'Resolve pending review before advancing' : 'Trigger next scammer + honeypot turn'}
            >
              {advancing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Generating Turn...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Advance Simulation Turn
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Pending Review Alert Banner if message held */}
      {pendingMessage && (
        <div className="bg-amber-50 border-2 border-warning/80 p-4 rounded-xl shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-warning/20 text-warning flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-ink">Action Held in Review Queue</h4>
              <p className="text-xs text-slate">
                The honeypot agent intercepted a <span className="font-bold text-warning">{pendingMessage.flagged_action}</span> and paused before delivery.
              </p>
            </div>
          </div>

          <button
            onClick={() => setSelectedMessageForReview(pendingMessage)}
            className="px-4 py-2 bg-warning text-white rounded-lg text-xs font-bold hover:bg-amber-700 active:scale-95 transition shadow-sm self-start sm:self-auto"
          >
            Review & Decide Now
          </button>
        </div>
      )}

      {/* Two-Column Layout (60% Transcript / 40% Intelligence Panel) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (60% width = 7 columns) */}
        <div className="lg:col-span-7 bg-surface border border-lineBorder rounded-xl p-5 shadow-sm flex flex-col h-[700px]">
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-lineBorder">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate">Live Decoy Transcript</h3>
            <span className="text-xs text-slate">End-to-End Chat Thread</span>
          </div>

          {/* Chat Bubbles Scroll Area */}
          <div className="flex-1 overflow-y-auto pr-2 space-y-2">
            {conversation.messages.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate text-sm">
                No turns recorded yet in this conversation.
              </div>
            ) : (
              conversation.messages.map((msg) => (
                <ConversationBubble
                  key={msg.id}
                  message={msg}
                  onOpenReview={(m) => setSelectedMessageForReview(m)}
                />
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </div>

        {/* Right Column (40% width = 5 columns) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Risk Score Gauge */}
          <RiskScoreGauge
            riskAssessment={conversation.risk_assessment}
            onExplain={handleExplain}
            isExplaining={explaining}
          />

          {/* Threat Indicators Table */}
          <IndicatorTable indicators={conversation.threat_indicators} />

          {/* Persona Card */}
          <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm text-xs">
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-lineBorder text-slate font-semibold uppercase tracking-wider">
              <UserCheck className="w-4 h-4 text-primary" />
              <span>Decoy Persona Profile: {conversation.persona_name}</span>
            </div>
            <div className="space-y-1 text-slate">
              <p><span className="font-semibold text-ink">Occupation:</span> {conversation.persona_backstory?.occupation || 'Retired'}</p>
              <p><span className="font-semibold text-ink">Financial Posture:</span> {conversation.persona_backstory?.financial_posture || 'Cautious, modest savings'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Review Modal */}
      <ReviewModal
        isOpen={!!selectedMessageForReview}
        message={selectedMessageForReview}
        onClose={() => setSelectedMessageForReview(null)}
        onActionComplete={fetchDetail}
      />
    </div>
  );
}
