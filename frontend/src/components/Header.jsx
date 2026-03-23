import { Menu, FlaskConical } from 'lucide-react';

export default function Header({ onMenuClick, sessionId, onNewAnalysis }) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-lg hover:bg-bg transition-colors text-text-secondary hover:text-text-primary"
        >
          <Menu size={20} />
        </button>
        <div className="flex items-center gap-2">
          <FlaskConical size={22} className="text-accent" />
          <span className="text-lg font-semibold tracking-tight">MARS</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {sessionId && (
          <span className="text-xs font-mono text-text-secondary">
            session: {sessionId.slice(0, 8)}
          </span>
        )}
        {sessionId && (
          <button
            onClick={onNewAnalysis}
            className="px-3 py-1.5 text-sm rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-accent transition-colors"
          >
            New Analysis
          </button>
        )}
      </div>
    </header>
  );
}
