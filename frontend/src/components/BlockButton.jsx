import React, { useState } from 'react';
import { ShieldX, Check, Loader2 } from 'lucide-react';

export default function BlockButton({ indicatorId, isBlocked, onBlockSuccess, onUnblockSuccess }) {
  const [loading, setLoading] = useState(false);

  const handleAction = async (e) => {
    e.stopPropagation();
    if (loading) return;

    setLoading(true);
    try {
      if (isBlocked && onUnblockSuccess) {
        await onUnblockSuccess(indicatorId);
      } else if (!isBlocked && onBlockSuccess) {
        await onBlockSuccess(indicatorId);
      }
    } finally {
      setLoading(false);
    }
  };

  if (isBlocked) {
    return (
      <button
        onClick={handleAction}
        disabled={loading}
        title="Click to unblock indicator"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-50 text-success border border-green-200 hover:bg-amber-50 hover:text-amber-800 hover:border-amber-300 group transition shadow-sm"
      >
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <>
            <Check className="w-3.5 h-3.5 group-hover:hidden" />
            <ShieldX className="w-3.5 h-3.5 hidden group-hover:inline text-amber-700" />
            <span className="group-hover:hidden">Blocked</span>
            <span className="hidden group-hover:inline font-bold">Unblock</span>
          </>
        )}
      </button>
    );
  }

  return (
    <button
      onClick={handleAction}
      disabled={loading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-danger text-white hover:bg-red-700 active:scale-95 transition disabled:opacity-50 shadow-sm"
    >
      {loading ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Blocking...
        </>
      ) : (
        <>
          <ShieldX className="w-3.5 h-3.5" />
          Block
        </>
      )}
    </button>
  );
}
