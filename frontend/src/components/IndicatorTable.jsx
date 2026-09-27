import React from 'react';
import { Globe, Phone, Wallet, DollarSign, ShieldAlert, CheckCircle2 } from 'lucide-react';

export default function IndicatorTable({ indicators = [] }) {
  if (!indicators || indicators.length === 0) {
    return (
      <div className="bg-surface border border-lineBorder rounded-xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate mb-2">
          Extracted Threat Indicators
        </h3>
        <p className="text-sm text-slate">
          No threat indicators (wallets, URLs, handles) extracted yet from this conversation.
        </p>
      </div>
    );
  }

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

  return (
    <div className="bg-surface border border-lineBorder rounded-xl overflow-hidden shadow-sm">
      <div className="p-4 border-b border-lineBorder flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-danger" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink">
            Extracted Threat Indicators
          </h3>
        </div>
        <span className="text-xs bg-gray-100 px-2 py-0.5 rounded text-slate font-medium">
          {indicators.length} detected
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 border-b border-lineBorder text-slate uppercase font-semibold">
            <tr>
              <th className="py-2.5 px-3">Type</th>
              <th className="py-2.5 px-3">Extracted Entity</th>
              <th className="py-2.5 px-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-lineBorder">
            {indicators.map((ind) => (
              <tr key={ind.id} className="hover:bg-gray-50/60 transition">
                <td className="py-2.5 px-3 whitespace-nowrap font-medium text-ink">
                  <div className="flex items-center gap-1.5">
                    {getTypeIcon(ind.indicator_type)}
                    <span>{formatTypeLabel(ind.indicator_type)}</span>
                  </div>
                </td>
                <td className="py-2.5 px-3 font-mono break-all text-ink selection:bg-yellow-200">
                  {ind.value}
                </td>
                <td className="py-2.5 px-3 whitespace-nowrap">
                  {ind.status === 'blocked' ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-green-100 text-success">
                      <CheckCircle2 className="w-3 h-3" />
                      BLOCKED
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-warning">
                      PENDING
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
