import AgentCard from './AgentCard';

export default function AgentDashboard({ agents, question }) {
  const phase1 = ['literature', 'data', 'hypothesis'];
  const phase2 = ['critique'];
  const phase3 = ['synthesis'];

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Research question */}
      <div className="mb-8">
        <p className="text-sm text-text-secondary mb-1">Research Question</p>
        <p className="text-lg font-medium">{question}</p>
      </div>

      {/* Phase 1 */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 1 — Parallel Analysis
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {phase1.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} />
          ))}
        </div>
      </div>

      {/* Phase 2 */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 2 — Evaluation
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {phase2.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} />
          ))}
        </div>
      </div>

      {/* Phase 3 */}
      <div>
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 3 — Synthesis
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {phase3.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} />
          ))}
        </div>
      </div>
    </div>
  );
}
