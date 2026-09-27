import React from 'react';
import { AlertTriangle, CheckCircle2, Edit3, ShieldAlert, XCircle, Image as ImageIcon } from 'lucide-react';

export default function ConversationBubble({ message, onOpenReview }) {
  const isPersona = message.role === 'persona';
  const isPending = message.review_status === 'pending';
  const isEdited = message.review_status === 'edited';
  const isHalted = message.review_status === 'halted';

  const formattedTime = message.created_at
    ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={`flex flex-col mb-4 ${isPersona ? 'items-end' : 'items-start'}`}>
      {/* Sender Label & Timestamp */}
      <div className="flex items-center gap-2 mb-1 px-1">
        <span className={`text-xs font-semibold uppercase tracking-wider ${isPersona ? 'text-primary' : 'text-slate'}`}>
          {isPersona ? 'Honeypot Persona' : 'Scammer (Suspect)'}
        </span>
        <span className="text-xs text-slate">{formattedTime}</span>
      </div>

      {/* Bubble Container */}
      <div
        className={`relative max-w-[80%] rounded-2xl p-4 text-[15px] leading-relaxed shadow-sm transition-all ${
          isPending
            ? 'bg-amber-50 border-2 border-warning text-ink ring-2 ring-warning/20 shadow-md'
            : isPersona
            ? 'bg-primary text-white rounded-br-sm'
            : 'bg-white text-ink border border-lineBorder rounded-bl-sm'
        }`}
      >
        {/* Pending Review Highlight Banner */}
        {isPending && (
          <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-warning/30 text-warning font-semibold text-xs uppercase tracking-wide">
            <span className="flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4" />
              Held for Human Review ({message.flagged_action || 'Sensitive Action'})
            </span>
            {onOpenReview && (
              <button
                onClick={() => onOpenReview(message)}
                className="px-2 py-0.5 bg-warning text-white rounded font-medium text-xs hover:bg-amber-700 transition"
              >
                Review Now
              </button>
            )}
          </div>
        )}

        {/* Message Content (with MMS Image highlighting) */}
        {message.text && message.text.includes('[Image:') ? (
          <div className="space-y-2">
            {message.text.split('[Image:').map((chunk, i) => {
              if (i === 0) {
                return chunk.trim() ? <p key={i} className="whitespace-pre-wrap">{chunk.trim()}</p> : null;
              }
              const [caption, ...rest] = chunk.split(']');
              return (
                <div key={i} className="space-y-1.5">
                  <div className={`p-2.5 rounded-lg border text-xs flex items-start gap-2 ${
                    isPersona ? 'bg-white/15 border-white/20 text-white' : 'bg-slate-50 border-lineBorder text-ink'
                  }`}>
                    <ImageIcon className={`w-4 h-4 shrink-0 mt-0.5 ${isPersona ? 'text-white' : 'text-primary'}`} />
                    <div>
                      <span className={`font-semibold block text-[10px] uppercase tracking-wider ${isPersona ? 'text-white/80' : 'text-slate'}`}>
                        MMS Attachment
                      </span>
                      <span className="leading-snug">{caption}</span>
                    </div>
                  </div>
                  {rest.join(']').trim() && (
                    <p className="whitespace-pre-wrap">{rest.join(']').trim()}</p>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{message.text}</p>
        )}

        {/* Status badges below bubble */}
        <div className="flex items-center gap-2 mt-2 pt-1">
          {message.flagged_action && !isPending && (
            <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded font-medium ${
              isPersona ? 'bg-white/20 text-white' : 'bg-red-50 text-danger border border-red-200'
            }`}>
              <ShieldAlert className="w-3 h-3" />
              {message.flagged_action}
            </span>
          )}

          {isEdited && (
            <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded font-medium ${
              isPersona ? 'bg-white/20 text-white' : 'bg-gray-100 text-slate'
            }`}>
              <Edit3 className="w-3 h-3" />
              Edited by analyst
            </span>
          )}

          {message.review_status === 'approved' && (
            <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded font-medium ${
              isPersona ? 'bg-white/20 text-white' : 'bg-green-50 text-success'
            }`}>
              <CheckCircle2 className="w-3 h-3" />
              Approved
            </span>
          )}

          {isHalted && (
            <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded font-medium bg-red-100 text-danger">
              <XCircle className="w-3 h-3" />
              Halted
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
