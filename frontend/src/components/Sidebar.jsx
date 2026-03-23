import { useEffect, useState } from 'react';
import { X, FileText } from 'lucide-react';
import { fetchSessions } from '../utils/api';

export default function Sidebar({ isOpen, onClose, onSelectSession }) {
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    if (isOpen) {
      fetchSessions().then(setSessions).catch(() => {});
    }
  }, [isOpen]);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed top-0 left-0 h-full w-80 bg-surface border-r border-border z-50 transform transition-transform duration-200 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
            Past Sessions
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-bg text-text-secondary hover:text-text-primary"
          >
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto h-[calc(100%-57px)]">
          {sessions.length === 0 ? (
            <p className="p-4 text-sm text-text-secondary">No sessions yet.</p>
          ) : (
            sessions.map(s => (
              <button
                key={s.session_id}
                onClick={() => { onSelectSession(s.session_id); onClose(); }}
                className="w-full text-left p-4 border-b border-border hover:bg-bg transition-colors"
              >
                <div className="flex items-start gap-2">
                  <FileText size={16} className="text-text-secondary mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-text-primary truncate">
                      {s.research_question}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        s.status === 'complete' ? 'bg-success/20 text-success' :
                        s.status === 'running' ? 'bg-warning/20 text-warning' :
                        s.status === 'error' ? 'bg-error/20 text-error' :
                        'bg-border text-text-secondary'
                      }`}>
                        {s.status}
                      </span>
                      <span className="text-xs text-text-secondary">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </>
  );
}
