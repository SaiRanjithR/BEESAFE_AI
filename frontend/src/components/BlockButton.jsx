import React, { useState } from 'react';
import { ShieldX, Check, Loader2 } from 'lucide-react';

export default function BlockButton({ indicatorId, isBlocked, onBlockSuccess }) {
  const [loading, setLoading] = useState(false);

  const handleBlock = async (e) => {
    e.stopPropagation();
    if (isBlocked || loading) return;

    setLoading(true);
    try {
      if (onBlockSuccess) {
        await onBlockSuccess(indicatorId);
      }
    } finally {
      setLoading(false);
    }
  };

  if (isBlocked) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-green-50 text-success border border-green-200">
        <Check className="w-3.5 h-3.5" />
        Blocked
      </span>
    );
  }

  return (
    <button
      onClick={handleBlock}
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
