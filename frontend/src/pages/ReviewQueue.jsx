import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Edit, AlertOctagon, RefreshCw, Loader2, ArrowRight } from 'lucide-react';
import { api } from '../api/client';
import ReviewModal from '../components/ReviewModal';

export default function ReviewQueue({ onSelectConversation }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedMessage, setSelectedMessage] = useState(null);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getReviewQueue();
      setItems(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch review queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">Human-in-the-Loop Review Queue</h1>
          <p className="text-sm text-slate mt-0.5">
            Intercepted persona replies held for human confirmation before outbound transmission.
          </p>
        </div>

        <button
          onClick={fetchQueue}
          disabled={loading}
          className="p-2 border border-lineBorder rounded-lg text-slate hover:bg-gray-100 transition"
          title="Refresh queue"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-danger rounded-xl text-xs font-medium">
          {error}
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="p-16 text-center text-slate flex flex-col items-center gap-3 bg-surface border border-lineBorder rounded-xl">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm">Fetching pending review actions...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="p-16 text-center text-slate flex flex-col items-center gap-3 bg-surface border border-lineBorder rounded-xl">
          <CheckCircle className="w-12 h-12 text-success/80" />
          <p className="text-base font-bold text-ink">Review Queue Clear</p>
          <p className="text-xs text-slate max-w-md">
            No persona replies are currently paused. When the honeypot encounters payment or platform move requests, they will hold here for your authorization.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-surface border-2 border-warning/60 rounded-xl p-5 shadow-sm hover:border-warning transition flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold text-ink font-mono">{item.scammer_contact}</span>
                  <span className="text-[11px] px-2 py-0.5 rounded font-bold uppercase bg-amber-100 text-warning border border-warning/30 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {item.flagged_action || 'Pending Approval'}
                  </span>
                  <span className="text-xs text-slate">Channel: {item.channel.toUpperCase()}</span>
                </div>

                <div className="p-3 bg-gray-50 border border-lineBorder rounded-lg text-sm text-ink font-sans">
                  <span className="text-xs text-slate uppercase font-semibold block mb-1">Generated Decoy Reply:</span>
                  &ldquo;{item.text}&rdquo;
                </div>
              </div>

              <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                {onSelectConversation && (
                  <button
                    onClick={() => onSelectConversation(item.conversation_id)}
                    className="p-2 border border-lineBorder rounded-lg text-slate hover:bg-gray-100 text-xs font-semibold flex items-center gap-1 transition"
                  >
                    Thread <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}

                <button
                  onClick={() => setSelectedMessage(item)}
                  className="px-4 py-2 bg-warning text-white rounded-lg text-xs font-bold hover:bg-amber-700 active:scale-95 transition shadow-sm"
                >
                  Review & Action
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Action Modal */}
      <ReviewModal
        isOpen={!!selectedMessage}
        message={selectedMessage}
        onClose={() => setSelectedMessage(null)}
        onActionComplete={fetchQueue}
      />
    </div>
  );
}
