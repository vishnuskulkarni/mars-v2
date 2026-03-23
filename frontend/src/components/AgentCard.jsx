import { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen, Database, Lightbulb, Shield, Layers } from 'lucide-react';

const AGENT_CONFIG = {
  literature: { icon: BookOpen, label: 'Literature', color: 'text-accent' },
  data: { icon: Database, label: 'Data', color: 'text-accent' },
  hypothesis: { icon: Lightbulb, label: 'Hypothesis', color: 'text-accent' },
  critique: { icon: Shield, label: 'Critique', color: 'text-accent' },
  synthesis: { icon: Layers, label: 'Synthesis', color: 'text-accent' },
};

const STATUS_STYLES = {
  pending: 'bg-border text-text-secondary',
  running: 'bg-warning/20 text-warning',
  complete: 'bg-success/20 text-success',
  error: 'bg-error/20 text-error',
};

export default function AgentCard({ name, agent }) {
  const [expanded, setExpanded] = useState(false);
  const config = AGENT_CONFIG[name] || { icon: Layers, label: name, color: 'text-accent' };
  const Icon = config.icon;

  const preview = agent.output
    ? agent.output.slice(0, 200) + (agent.output.length > 200 ? '...' : '')
    : '';

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icon size={18} className={config.color} />
            <span className="font-medium text-sm">{config.label}</span>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[agent.status]}`}>
            {agent.status}
          </span>
        </div>

        {/* Progress bar */}
        {agent.status === 'running' && (
          <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-warning to-accent rounded-full transition-all duration-300"
              style={{ width: `${Math.max(agent.progress, 5)}%` }}
            />
          </div>
        )}

        {agent.status === 'complete' && (
          <div className="w-full h-1.5 bg-success/20 rounded-full overflow-hidden">
            <div className="h-full bg-success rounded-full w-full" />
          </div>
        )}
      </div>

      {/* Output preview / expanded */}
      {(agent.output || agent.error) && (
        <div className="border-t border-border">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between px-4 py-2 text-xs text-text-secondary hover:bg-bg/50 transition-colors"
          >
            <span>{expanded ? 'Collapse' : 'Expand output'}</span>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {!expanded && preview && (
            <p className="px-4 pb-3 text-xs text-text-secondary leading-relaxed line-clamp-3">
              {preview}
            </p>
          )}

          {expanded && (
            <div className="px-4 pb-4 max-h-96 overflow-y-auto">
              <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono leading-relaxed">
                {agent.error || agent.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
