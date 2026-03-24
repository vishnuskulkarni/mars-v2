import AgentCard from './AgentCard';

export default function AgentDashboard({ agents, question, onFeedback, isRevising }) {
  const phase1 = ['literature', 'data', 'hypothesis', 'methods', 'scout'];
  const phase2 = ['critique'];
  const phase3 = ['synthesis'];
  const phase4 = ['output'];

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
          {phase1.slice(0, 3).map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} onFeedback={onFeedback} feedbackDisabled={isRevising} />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {phase1.slice(3).map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} onFeedback={onFeedback} feedbackDisabled={isRevising} />
          ))}
        </div>
      </div>

      {/* Phase 2 */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 2 — Evaluation
        </h3>
        <div className="max-w-xl">
          {phase2.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} onFeedback={onFeedback} feedbackDisabled={isRevising} />
          ))}
        </div>
      </div>

      {/* Phase 3 */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 3 — Integration
        </h3>
        <div className="max-w-xl">
          {phase3.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} onFeedback={onFeedback} feedbackDisabled={isRevising} />
          ))}
        </div>
      </div>

      {/* Phase 4 */}
      <div>
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          Phase 4 — Report
        </h3>
        <div className="max-w-xl">
          {phase4.map(name => (
            <AgentCard key={name} name={name} agent={agents[name]} onFeedback={onFeedback} feedbackDisabled={isRevising} />
          ))}
        </div>
      </div>
    </div>
  );
}
