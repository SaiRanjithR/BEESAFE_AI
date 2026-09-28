import React, { useState, useEffect, useMemo } from 'react';
import {
  Building2,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Search,
  Filter,
  ArrowUpDown,
  RefreshCw,
  Copy,
  Check,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Wallet,
  Globe,
  Phone,
  DollarSign,
  Info,
  CheckCircle2,
  Clock,
  Layers,
  RotateCcw,
} from 'lucide-react';
import { api } from '../api/client';
import BlockButton from '../components/BlockButton';

export default function InstitutionDashboard() {
  const [indicators, setIndicators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [minRiskFilter, setMinRiskFilter] = useState('all');
  const [onlyCorrelated, setOnlyCorrelated] = useState(false);
  const [sortBy, setSortBy] = useState('risk_desc');
  const [copiedId, setCopiedId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [notification, setNotification] = useState(null);

  const fetchIndicators = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const data = await api.listIndicators();
      setIndicators(data);
    } catch (err) {
      console.error('Failed to fetch indicators:', err);
      setError(err.message || 'Failed to load threat indicators from the security API.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchIndicators();
  }, []);

  const handleBlock = async (indicatorId) => {
    try {
      const res = await api.blockIndicator(indicatorId);
      // Update local state without full reload
      setIndicators((prev) =>
        prev.map((ind) => (ind.id === indicatorId ? { ...ind, status: 'blocked' } : ind))
      );
      setNotification({
        type: 'success',
        message:
          res.status === 'already_blocked'
            ? 'Indicator was already flagged as blocked (idempotent; no duplicate audit log).'
            : 'Enforcement rule activated: Indicator marked as BLOCKED and recorded in tamper-evident audit logs.',
      });
      setTimeout(() => setNotification(null), 5000);
    } catch (err) {
      console.error('Failed to block indicator:', err);
      setNotification({
        type: 'error',
        message: err.message || 'Failed to apply block rule.',
      });
      setTimeout(() => setNotification(null), 5000);
    }
  };

  const handleUnblock = async (indicatorId) => {
    try {
      await api.unblockIndicator(indicatorId);
      setIndicators((prev) =>
        prev.map((ind) => (ind.id === indicatorId ? { ...ind, status: 'pending' } : ind))
      );
      setNotification({
        type: 'success',
        message: 'Enforcement status reset: Indicator marked as PENDING (unblocked).',
      });
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      console.error('Failed to unblock indicator:', err);
      setNotification({
        type: 'error',
        message: err.message || 'Failed to unblock indicator.',
      });
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const handleResetAll = async () => {
    if (!window.confirm("Reset all threat indicators back to 'PENDING'? This allows you to test the Block action on fresh indicators.")) {
      return;
    }
    try {
      setRefreshing(true);
      await api.resetAllIndicators();
      await fetchIndicators(false);
      setNotification({
        type: 'success',
        message: 'All threat indicators have been reset to PENDING. Block buttons are now ready to test.',
      });
      setTimeout(() => setNotification(null), 4000);
    } catch (err) {
      console.error('Failed to reset indicators:', err);
      setNotification({
        type: 'error',
        message: err.message || 'Failed to reset indicators.',
      });
    } finally {
      setRefreshing(false);
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'crypto_wallet':
        return <Wallet className="w-4 h-4 text-purple-600" />;
      case 'url':
        return <Globe className="w-4 h-4 text-blue-600" />;
      case 'phone_number':
        return <Phone className="w-4 h-4 text-green-600" />;
      case 'payment_handle':
        return <DollarSign className="w-4 h-4 text-emerald-600" />;
      default:
        return <ShieldAlert className="w-4 h-4 text-slate" />;
    }
  };

  const formatTypeLabel = (type) => {
    switch (type) {
      case 'crypto_wallet':
        return 'Crypto Wallet';
      case 'url':
        return 'URL / Portal';
      case 'phone_number':
        return 'Phone Number';
      case 'payment_handle':
        return 'Payment Handle';
      default:
        return type;
    }
  };

  const getRiskBadge = (score) => {
    if (score === null || score === undefined) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-100 text-slate">
          Unrated
        </span>
      );
    }
    if (score >= 70) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-danger border border-red-200">
          <AlertTriangle className="w-3 h-3" />
          {score} / 100
        </span>
      );
    }
    if (score >= 30) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-warning border border-amber-200">
          {score} / 100
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-green-100 text-success border border-green-200">
        {score} / 100
      </span>
    );
  };

  // Filter & Sort Logic
  const filteredIndicators = useMemo(() => {
    let result = [...indicators];

    // Search filter
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      result = result.filter(
        (ind) =>
          ind.value.toLowerCase().includes(q) ||
          ind.indicator_type.toLowerCase().includes(q) ||
          (ind.risk_classification && ind.risk_classification.toLowerCase().includes(q))
      );
    }

    // Type filter
    if (selectedType !== 'all') {
      result = result.filter((ind) => ind.indicator_type === selectedType);
    }

    // Status filter
    if (selectedStatus !== 'all') {
      result = result.filter((ind) => ind.status === selectedStatus);
    }

    // Min Risk filter
    if (minRiskFilter === 'high') {
      result = result.filter((ind) => (ind.risk_score || 0) >= 70);
    } else if (minRiskFilter === 'medium') {
      result = result.filter((ind) => (ind.risk_score || 0) >= 30 && (ind.risk_score || 0) < 70);
    } else if (minRiskFilter === 'low') {
      result = result.filter((ind) => (ind.risk_score || 0) < 30);
    }

    // Correlated Only filter
    if (onlyCorrelated) {
      result = result.filter((ind) => (ind.conversation_count || 1) > 1);
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'correlated_desc') {
        const countA = a.conversation_count || 1;
        const countB = b.conversation_count || 1;
        if (countB !== countA) return countB - countA;
        const scoreA = a.risk_score ?? -1;
        const scoreB = b.risk_score ?? -1;
        return scoreB - scoreA;
      }
      if (sortBy === 'risk_desc') {
        const scoreA = a.risk_score ?? -1;
        const scoreB = b.risk_score ?? -1;
        if (scoreB !== scoreA) return scoreB - scoreA;
        return new Date(b.created_at) - new Date(a.created_at);
      }
      if (sortBy === 'risk_asc') {
        const scoreA = a.risk_score ?? 999;
        const scoreB = b.risk_score ?? 999;
        if (scoreA !== scoreB) return scoreA - scoreB;
        return new Date(b.created_at) - new Date(a.created_at);
      }
      if (sortBy === 'created_desc') {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      if (sortBy === 'created_asc') {
        return new Date(a.created_at) - new Date(b.created_at);
      }
      return 0;
    });

    return result;
  }, [indicators, searchTerm, selectedType, selectedStatus, minRiskFilter, onlyCorrelated, sortBy]);

  // Statistics
  const totalCount = indicators.length;
  const highRiskCount = indicators.filter((ind) => (ind.risk_score || 0) >= 70).length;
  const correlatedCount = indicators.filter((ind) => (ind.conversation_count || 1) > 1).length;
  const blockedCount = indicators.filter((ind) => ind.status === 'blocked').length;
  const pendingCount = indicators.filter((ind) => ind.status === 'pending').length;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-ink tracking-tight">
              Institution Threat Intelligence Feed
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
              <Building2 className="w-3.5 h-3.5" />
              SecOps Node
            </span>
          </div>
          <p className="text-sm text-slate mt-1">
            Real-time feed of malicious payment handles, crypto wallets, phishing portals, and phone numbers.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleResetAll}
            disabled={refreshing}
            title="Reset all indicators back to Pending state for demo testing"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-surface border border-lineBorder text-slate hover:text-ink hover:bg-gray-50 active:scale-95 transition disabled:opacity-50 shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate" />
            Reset to Pending
          </button>

          <button
            onClick={() => fetchIndicators(false)}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-surface border border-lineBorder text-ink hover:bg-gray-50 active:scale-95 transition disabled:opacity-50 shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Feed
          </button>
        </div>
      </div>

      {/* Security & Privacy Role Separation Notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-xs text-blue-900 flex items-start gap-3 shadow-sm">
        <Info className="w-5 h-5 text-primary shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-blue-950">
            Privacy Boundary Enforced (Security & Access Document §2)
          </p>
          <p className="text-blue-800 leading-relaxed">
            Honeypot conversation transcripts and persona backstories are strictly quarantined. Financial institutions receive verified indicator artifacts, fraud classification, and algorithmic risk telemetry only.
          </p>
        </div>
      </div>

      {/* Notification Toast */}
      {notification && (
        <div
          className={`p-3.5 rounded-xl border text-xs font-medium flex items-center justify-between shadow-sm transition animate-in fade-in ${
            notification.type === 'error'
              ? 'bg-red-50 border-red-200 text-danger'
              : 'bg-green-50 border-green-200 text-green-900'
          }`}
        >
          <div className="flex items-center gap-2">
            {notification.type === 'error' ? (
              <ShieldAlert className="w-4 h-4 text-danger shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-slate hover:text-ink font-bold ml-4"
          >
            ×
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate">
            Total Indicators
          </span>
          <div className="text-2xl font-bold text-ink mt-1">{totalCount}</div>
          <span className="text-[11px] text-slate mt-0.5 block">Extracted from decoys</span>
        </div>

        <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-danger">
            High Risk (70+)
          </span>
          <div className="text-2xl font-bold text-danger mt-1">{highRiskCount}</div>
          <span className="text-[11px] text-slate mt-0.5 block">Priority block candidates</span>
        </div>

        <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-purple-600">
            Correlated Threats
          </span>
          <div className="text-2xl font-bold text-purple-700 mt-1">{correlatedCount}</div>
          <span className="text-[11px] text-slate mt-0.5 block">Seen in &gt;1 conversation</span>
        </div>

        <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-success">
            Active Block Rules
          </span>
          <div className="text-2xl font-bold text-success mt-1">{blockedCount}</div>
          <span className="text-[11px] text-slate mt-0.5 block">Enforced at institution</span>
        </div>

        <div className="bg-surface border border-lineBorder rounded-xl p-4 shadow-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-warning">
            Pending Action
          </span>
          <div className="text-2xl font-bold text-warning mt-1">{pendingCount}</div>
          <span className="text-[11px] text-slate mt-0.5 block">Awaiting SecOps review</span>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="bg-surface border border-lineBorder rounded-xl p-4 space-y-3 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search bar */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search wallet, URL, phone number, handle..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-lineBorder bg-background focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
            />
          </div>

          {/* Sort & Quick Filter Selectors */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setOnlyCorrelated(!onlyCorrelated)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
                onlyCorrelated
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'bg-surface border border-lineBorder text-slate hover:text-ink hover:bg-gray-50'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Correlated Only ({correlatedCount})</span>
            </button>

            <div className="flex items-center gap-1.5 text-xs text-slate">
              <ArrowUpDown className="w-3.5 h-3.5 text-slate" />
              <span>Sort:</span>
            </div>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="text-xs rounded-lg border border-lineBorder bg-surface px-2.5 py-1.5 text-ink font-medium focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="risk_desc">Risk Score (Highest First)</option>
              <option value="risk_asc">Risk Score (Lowest First)</option>
              <option value="correlated_desc">Most Correlated First</option>
              <option value="created_desc">Newest First</option>
              <option value="created_asc">Oldest First</option>
            </select>

            <select
              value={minRiskFilter}
              onChange={(e) => setMinRiskFilter(e.target.value)}
              className="text-xs rounded-lg border border-lineBorder bg-surface px-2.5 py-1.5 text-ink font-medium focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="all">All Risk Levels</option>
              <option value="high">High Risk (70+)</option>
              <option value="medium">Medium Risk (30–70)</option>
              <option value="low">Low Risk (&lt;30)</option>
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="text-xs rounded-lg border border-lineBorder bg-surface px-2.5 py-1.5 text-ink font-medium focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending Only</option>
              <option value="blocked">Blocked Only</option>
            </select>
          </div>
        </div>

        {/* Entity Type Chips */}
        <div className="flex items-center gap-1.5 pt-2 border-t border-lineBorder overflow-x-auto text-xs">
          <span className="text-slate font-medium mr-1 text-[11px] uppercase tracking-wider">
            Entity Type:
          </span>
          {[
            { id: 'all', label: 'All Entities' },
            { id: 'crypto_wallet', label: 'Crypto Wallets' },
            { id: 'url', label: 'URLs / Portals' },
            { id: 'phone_number', label: 'Phone Numbers' },
            { id: 'payment_handle', label: 'Payment Handles' },
          ].map((type) => (
            <button
              key={type.id}
              onClick={() => setSelectedType(type.id)}
              className={`px-3 py-1 rounded-full whitespace-nowrap font-medium transition ${
                selectedType === type.id
                  ? 'bg-ink text-white shadow-sm'
                  : 'bg-gray-100 text-slate hover:bg-gray-200'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Indicators Table */}
      <div className="bg-surface border border-lineBorder rounded-xl overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-slate">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
            <p className="text-xs font-medium">Loading threat intelligence feed...</p>
          </div>
        ) : error ? (
          <div className="p-10 text-center space-y-3">
            <ShieldAlert className="w-8 h-8 text-danger mx-auto" />
            <p className="text-sm font-semibold text-ink">{error}</p>
            <button
              onClick={() => fetchIndicators(true)}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primaryHover transition"
            >
              Retry Connection
            </button>
          </div>
        ) : filteredIndicators.length === 0 ? (
          <div className="p-12 text-center text-slate space-y-2">
            <ShieldCheck className="w-8 h-8 text-success mx-auto" />
            <p className="text-sm font-semibold text-ink">No matching threat indicators</p>
            <p className="text-xs text-slate">
              Try adjusting your search query, risk filters, or entity type chips.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-lineBorder text-slate uppercase font-semibold">
                <tr>
                  <th className="py-3 px-4">Entity Type</th>
                  <th className="py-3 px-4">Extracted Value</th>
                  <th className="py-3 px-4">Source Risk Score</th>
                  <th className="py-3 px-4">Classification</th>
                  <th className="py-3 px-4">First Detected</th>
                  <th className="py-3 px-4">Enforcement Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-lineBorder">
                {filteredIndicators.map((ind) => {
                  const isExpanded = expandedId === ind.id;
                  const hasReasons = ind.risk_reasons && ind.risk_reasons.length > 0;

                  return (
                    <React.Fragment key={ind.id}>
                      <tr className="hover:bg-gray-50/70 transition">
                        {/* Entity Type */}
                        <td className="py-3 px-4 whitespace-nowrap font-medium text-ink">
                          <div className="flex items-center gap-2">
                            {getTypeIcon(ind.indicator_type)}
                            <span>{formatTypeLabel(ind.indicator_type)}</span>
                          </div>
                        </td>

                        {/* Extracted Value */}
                        <td className="py-3 px-4 font-mono text-ink">
                          <div className="flex flex-col gap-1.5">
                            <div className="flex items-center gap-2 max-w-md">
                              <span className="truncate select-all bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
                                {ind.value}
                              </span>
                              <button
                                onClick={() => copyToClipboard(ind.value, ind.id)}
                                title="Copy to clipboard"
                                className="text-slate hover:text-ink transition shrink-0"
                              >
                                {copiedId === ind.id ? (
                                  <Check className="w-3.5 h-3.5 text-success" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>
                              {ind.indicator_type === 'url' && (
                                <a
                                  href={ind.value}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title="Open URL in new tab (caution)"
                                  className="text-primary hover:text-primaryHover transition shrink-0"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {ind.conversation_count > 1 && (
                                <span
                                  title={`Cross-campaign threat: observed in ${ind.conversation_count} separate honeypot conversations`}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-700 border border-purple-200"
                                >
                                  <Layers className="w-3 h-3 text-purple-600" />
                                  seen in {ind.conversation_count} conversations
                                </span>
                              )}
                              {ind.indicator_type === 'url' && ind.domain_age_days !== null && ind.domain_age_days !== undefined && (
                                <span
                                  title={`RDAP WHOIS: domain was registered ${ind.domain_age_days} days ago`}
                                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                    ind.domain_age_days <= 14
                                      ? 'bg-amber-100 text-amber-900 border-amber-300'
                                      : 'bg-gray-100 text-slate border-gray-200'
                                  }`}
                                >
                                  <Clock className="w-2.5 h-2.5" />
                                  {ind.domain_age_days <= 14 ? `New Domain (${ind.domain_age_days}d)` : `Domain: ${ind.domain_age_days}d`}
                                </span>
                              )}
                              {ind.indicator_type === 'url' && ind.known_bad === true && (
                                <span
                                  title="Flagged on public threat blocklists (URLhaus / RDAP)"
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-danger border border-red-200"
                                >
                                  <ShieldAlert className="w-2.5 h-2.5" />
                                  Blocklist Flagged
                                </span>
                              )}
                              {ind.indicator_type === 'url' && ind.known_bad === false && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-50 text-green-700 border border-green-200">
                                  Blocklist Clean
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Risk Score */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {getRiskBadge(ind.risk_score)}
                            {hasReasons && (
                              <button
                                onClick={() => setExpandedId(isExpanded ? null : ind.id)}
                                title="View algorithmic risk evidence"
                                className="text-slate hover:text-ink text-[11px] font-medium flex items-center gap-0.5 ml-1"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="w-3.5 h-3.5" />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5" />
                                )}
                              </button>
                            )}
                          </div>
                        </td>

                        {/* Classification */}
                        <td className="py-3 px-4 whitespace-nowrap text-slate font-medium">
                          {ind.risk_classification ? (
                            <span className="px-2 py-0.5 rounded bg-gray-100 text-ink text-[11px]">
                              {ind.risk_classification.replace(/_/g, ' ')}
                            </span>
                          ) : (
                            <span className="text-slate italic">pending analysis</span>
                          )}
                        </td>

                        {/* First Detected */}
                        <td className="py-3 px-4 whitespace-nowrap text-slate">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3 h-3 text-slate/70" />
                            <span>
                              {new Date(ind.created_at).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                          </div>
                        </td>

                        {/* Enforcement Status */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {ind.status === 'blocked' ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-success border border-green-200">
                              <CheckCircle2 className="w-3 h-3" />
                              BLOCKED
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-warning border border-amber-200">
                              PENDING
                            </span>
                          )}
                        </td>

                        {/* Action: Block Button */}
                        <td className="py-3 px-4 whitespace-nowrap text-right">
                          <BlockButton
                            indicatorId={ind.id}
                            isBlocked={ind.status === 'blocked'}
                            onBlockSuccess={() => handleBlock(ind.id)}
                            onUnblockSuccess={() => handleUnblock(ind.id)}
                          />
                        </td>
                      </tr>

                      {/* Expandable Evidence Row */}
                      {isExpanded && hasReasons && (
                        <tr className="bg-blue-50/40 border-b border-lineBorder">
                          <td colSpan="7" className="py-3 px-6">
                            <div className="space-y-1.5">
                              <span className="text-[11px] font-bold text-slate uppercase tracking-wider">
                                Algorithmic Risk Evidence:
                              </span>
                              <ul className="list-disc list-inside space-y-1 text-ink text-xs pl-1">
                                {ind.risk_reasons.map((reason, idx) => (
                                  <li key={idx} className="leading-relaxed">
                                    {reason}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
