import { useState, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatInput from './components/ChatInput';
import AgentDashboard from './components/AgentDashboard';
import ReportView from './components/ReportView';
import { useSSE } from './hooks/useSSE';
import { useSession } from './hooks/useSession';
import { submitResearch, fetchReport } from './utils/api';

function App() {
  const [view, setView] = useState('input'); // 'input' | 'running' | 'report'
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { sessionId, setSessionId, agents, reportReady, handleEvent, reset } = useSession();

  // Connect SSE when we have a session
  const onSSEEvent = useCallback((event) => {
    handleEvent(event);
    if (event.type === 'report_ready') {
      setView('report');
    }
  }, [handleEvent]);

  useSSE(view === 'running' ? sessionId : null, onSSEEvent);

  const handleSubmit = async (q, litFiles, dataFiles) => {
    setIsSubmitting(true);
    setQuestion(q);
    try {
      const { session_id } = await submitResearch(q, litFiles, dataFiles);
      setSessionId(session_id);
      setView('running');
    } catch (err) {
      alert('Failed to submit: ' + err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNewAnalysis = () => {
    reset();
    setView('input');
    setQuestion('');
  };

  const handleSelectSession = async (sid) => {
    setSessionId(sid);
    try {
      const report = await fetchReport(sid);
      setQuestion(report.research_question);
      setView('report');
    } catch {
      // Session might still be running, go to dashboard view
      setView('running');
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <Header
        onMenuClick={() => setSidebarOpen(true)}
        sessionId={sessionId}
        onNewAnalysis={handleNewAnalysis}
      />

      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSelectSession={handleSelectSession}
      />

      {view === 'input' && (
        <ChatInput onSubmit={handleSubmit} isLoading={isSubmitting} />
      )}

      {view === 'running' && (
        <AgentDashboard agents={agents} question={question} />
      )}

      {view === 'report' && sessionId && (
        <ReportView sessionId={sessionId} />
      )}
    </div>
  );
}

export default App;
