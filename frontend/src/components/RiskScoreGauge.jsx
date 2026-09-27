import React from 'react';
import { ShieldAlert, ShieldCheck, AlertCircle, Sparkles, RefreshCw, Loader2 } from 'lucide-react';

export default function RiskScoreGauge({ riskAssessment, onExplain, isExplaining = false }) {
  if (!riskAssessment) {
    return (
      <div className="bg-surface border border-lineBorder rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate">Fraud Risk Score</h3>
          <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-gray-100 text-slate">Pending</span>
        </div>
        <p className="text-sm text-slate">Risk scoring will run as conversation messages accumulate.</p>
      </div>
    );
  }

  const { risk_score, classification, reasons, explanation, updated_at } = riskAssessment;

  // Palette rule: green < 30, amber 30-70, red > 70
  let colorClass = 'text-success';
  let bgClass = 'bg-green-50 border-green-200';
  let badgeClass = 'bg-green-100 text-success';
  let badgeLabel = 'LOW RISK';
  let Icon = ShieldCheck;

  if (risk_score >= 70) {
    colorClass = 'text-danger';
    bgClass = 'bg-red-50 border-red-200';
    badgeClass = 'bg-red-100 text-danger';
    badgeLabel = 'HIGH RISK — FRAUD SUSPECTED';
    Icon = ShieldAlert;
  } else if (risk_score >= 30) {
    colorClass = 'text-warning';
    bgClass = 'bg-amber-50 border-amber-200';
    badgeClass = 'bg-amber-100 text-warning';
    badgeLabel = 'SUSPICIOUS ACTIVITY';
    Icon = AlertCircle;
  }

  const formattedUpdated = updated_at
    ? new Date(updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  return (
    <div className={`border rounded-xl p-5 shadow-sm transition-all ${bgClass}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${colorClass}`} />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink">Risk Assessment</h3>
        </div>
        <span className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${badgeClass}`}>
          {badgeLabel}
        </span>
      </div>

      {/* Main Score & Classification */}
      <div className="flex items-baseline gap-3 my-2">
        <span className={`text-[40px] font-[800] leading-none ${colorClass}`}>
          {risk_score}
        </span>
        <span className="text-slate text-sm font-medium">/ 100</span>
        <span className="text-xs text-slate ml-auto font-mono">
          {classification}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden my-3">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            risk_score >= 70 ? 'bg-danger' : risk_score >= 30 ? 'bg-warning' : 'bg-success'
          }`}
          style={{ width: `${Math.min(Math.max(risk_score, 5), 100)}%` }}
        />
      </div>

      {/* Narrative Explanation Briefing (TICKET-012) */}
      {explanation ? (
        <div className="mt-4 p-3.5 bg-white/80 border border-lineBorder rounded-lg shadow-sm">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-primary uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Narrative Threat Briefing</span>
            </div>
            {onExplain && (
              <button
                onClick={onExplain}
                disabled={isExplaining}
                className="text-[11px] text-slate hover:text-ink flex items-center gap-1 transition"
                title="Regenerate narrative briefing"
              >
                {isExplaining ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                Regenerate
              </button>
            )}
          </div>
          <p className="text-xs text-ink leading-relaxed font-normal">
            {explanation}
          </p>
        </div>
      ) : onExplain && (
        <div className="mt-4 pt-3 border-t border-lineBorder/50 flex items-center justify-between">
          <span className="text-xs text-slate">Executive narrative summary:</span>
          <button
            onClick={onExplain}
            disabled={isExplaining}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-white border border-lineBorder text-ink hover:bg-gray-50 active:scale-95 transition shadow-2xs"
          >
            {isExplaining ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin text-primary" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-3 h-3 text-amber-500" />
                Generate Briefing
              </>
            )}
          </button>
        </div>
      )}

      {/* Plain Language Reasons (Kept alongside narrative) */}
      {reasons && reasons.length > 0 && (
        <div className="mt-4 pt-3 border-t border-lineBorder/50">
          <h4 className="text-xs font-semibold text-slate uppercase tracking-wider mb-2">
            Transcript-Grounded Evidence:
          </h4>
          <ul className="space-y-1.5 text-xs text-ink">
            {reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-primary font-bold">•</span>
                <span className="leading-relaxed">{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {formattedUpdated && (
        <div className="mt-3 pt-2 text-right">
          <span className="text-[11px] text-slate">Last updated: {formattedUpdated}</span>
        </div>
      )}
    </div>
  );
}
