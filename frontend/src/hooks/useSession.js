import { useState, useCallback } from 'react';

const AGENT_NAMES = ['literature', 'data', 'hypothesis', 'critique', 'synthesis'];

function initialAgentState() {
  const agents = {};
  AGENT_NAMES.forEach(name => {
    agents[name] = { status: 'pending', output: '', progress: 0 };
  });
  return agents;
}

export function useSession() {
  const [sessionId, setSessionId] = useState(null);
  const [agents, setAgents] = useState(initialAgentState);
  const [reportReady, setReportReady] = useState(false);

  const handleEvent = useCallback((event) => {
    if (event.type === 'report_ready') {
      setReportReady(true);
      return;
    }

    const agentName = event.agent;
    if (!agentName || !AGENT_NAMES.includes(agentName)) return;

    setAgents(prev => {
      const updated = { ...prev };
      const agent = { ...updated[agentName] };

      if (event.type === 'status') {
        agent.status = event.content || 'running';
        if (event.progress != null) agent.progress = event.progress;
      } else if (event.type === 'chunk') {
        agent.status = 'running';
        agent.output += event.content || '';
        // Estimate progress based on output length (rough heuristic)
        agent.progress = Math.min(90, Math.floor(agent.output.length / 50));
      } else if (event.type === 'complete') {
        agent.status = 'complete';
        agent.progress = 100;
        if (event.content) agent.output = event.content;
      } else if (event.type === 'error') {
        agent.status = 'error';
        agent.error = event.content;
      }

      updated[agentName] = agent;
      return updated;
    });
  }, []);

  const reset = useCallback(() => {
    setSessionId(null);
    setAgents(initialAgentState());
    setReportReady(false);
  }, []);

  return { sessionId, setSessionId, agents, reportReady, handleEvent, reset };
}
