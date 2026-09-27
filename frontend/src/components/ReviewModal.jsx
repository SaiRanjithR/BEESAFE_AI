import React, { useState } from 'react';
import { X, CheckCircle, Edit, AlertOctagon, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export default function ReviewModal({ message, isOpen, onClose, onActionComplete }) {
  if (!isOpen || !message) return null;

  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(message.text || '');
  const [loadingAction, setLoadingAction] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const handleApprove = async () => {
    setLoadingAction('approve');
    setErrorMessage('');
    try {
      await api.approveMessage(message.id);
      if (onActionComplete) onActionComplete();
      onClose();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to approve message');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editedText.trim()) return;

    setLoadingAction('edit');
    setErrorMessage('');
    try {
      await api.editMessage(message.id, editedText.trim());
      if (onActionComplete) onActionComplete();
      onClose();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit edited reply');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleHalt = async () => {
    if (!window.confirm('Are you sure you want to HALT this conversation? No further messages will be sent.')) {
      return;
    }
    setLoadingAction('halt');
    setErrorMessage('');
    try {
      await api.haltMessage(message.id);
      if (onActionComplete) onActionComplete();
      onClose();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to halt conversation');
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-xl border border-lineBorder overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-lineBorder bg-gray-50/50">
          <div>
            <h3 className="text-base font-bold text-ink">Human-in-the-Loop Review</h3>
            <p className="text-xs text-slate">Action held: {message.flagged_action || 'Sensitive turn'}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate hover:bg-gray-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {errorMessage && (
            <div className="p-3 bg-red-50 border border-red-200 text-danger rounded-lg text-xs leading-relaxed font-medium">
              {errorMessage}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate mb-1">
              Proposed Honeypot Reply:
            </label>
            {isEditing ? (
              <form onSubmit={handleEditSubmit} className="space-y-3">
                <textarea
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  rows={4}
                  className="w-full text-sm p-3 border border-lineBorder rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent font-sans"
                  placeholder="Enter edited response text..."
                  autoFocus
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditing(false);
                      setEditedText(message.text);
                    }}
                    className="px-3 py-1.5 border border-lineBorder rounded-lg text-xs text-ink hover:bg-gray-100 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loadingAction === 'edit' || !editedText.trim()}
                    className="px-4 py-1.5 bg-primary text-white rounded-lg text-xs font-semibold hover:bg-primary-hover disabled:opacity-50 transition flex items-center gap-1.5"
                  >
                    {loadingAction === 'edit' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                    Save & Send Edited Reply
                  </button>
                </div>
              </form>
            ) : (
              <div className="p-3 bg-amber-50/50 border border-warning/30 rounded-lg text-sm text-ink leading-relaxed">
                {message.text}
              </div>
            )}
          </div>

          {!isEditing && (
            <div className="pt-2 text-xs text-slate">
              <span className="font-semibold text-ink">Analyst Guidance:</span> Approving will deliver this reply immediately. If you need to revise wording or keep the scammer hooked without risking disclosure, click <span className="font-medium text-ink">Edit Reply</span>.
            </div>
          )}
        </div>

        {/* Footer Actions */}
        {!isEditing && (
          <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-t border-lineBorder">
            <button
              onClick={handleHalt}
              disabled={loadingAction !== null}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-danger text-white hover:bg-red-700 transition active:scale-95 disabled:opacity-50"
            >
              {loadingAction === 'halt' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertOctagon className="w-3.5 h-3.5" />}
              Halt Operation
            </button>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsEditing(true)}
                disabled={loadingAction !== null}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold border border-lineBorder bg-white text-ink hover:bg-gray-100 transition active:scale-95 disabled:opacity-50"
              >
                <Edit className="w-3.5 h-3.5" />
                Edit Reply
              </button>

              <button
                onClick={handleApprove}
                disabled={loadingAction !== null}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary-hover transition active:scale-95 disabled:opacity-50 shadow-sm"
              >
                {loadingAction === 'approve' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                Approve & Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
