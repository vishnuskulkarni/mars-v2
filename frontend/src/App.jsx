import { useState, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatInput from './components/ChatInput';
import AgentDashboard from './components/AgentDashboard';
import ReportView from './components/ReportView';
import { useSSE } from './hooks/useSSE';
import { useSession } from './hooks/useSession';
import { submitResearch, fetchReport, submitFeedback } from './utils/api';

function App() {
  const [view, setView] = useState('input'); // 'input' | 'running' | 'report'
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevising, setIsRevising] = useState(false);

  const { sessionId, setSessionId, agents, reportReady, setReportReady, handleEvent, reset } = useSession();

  // Connect SSE when we have a running session
  const onSSEEvent = useCallback((event) => {
    handleEvent(event);
    if (event.type === 'report_ready') {
      setView('report');
      setIsRevising(false);
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
    setIsRevising(false);
  };

  const handleSelectSession = async (sid) => {
    setSessionId(sid);
    try {
      const report = await fetchReport(sid);
      setQuestion(report.research_question);
      setView('report');
    } catch {
      setView('running');
    }
  };

  const handleFeedback = async (agentName, feedbackText) => {
    if (!sessionId) return;
    try {
      setIsRevising(true);
      setReportReady(false);
      await submitFeedback(sessionId, agentName, feedbackText);
      // Switch to running view to show SSE updates
      setView('running');
    } catch (err) {
      alert('Feedback failed: ' + err.message);
      setIsRevising(false);
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
        <AgentDashboard
          agents={agents}
          question={question}
          onFeedback={handleFeedback}
          isRevising={isRevising}
        />
      )}

      {view === 'report' && sessionId && (
        <ReportView sessionId={sessionId} />
      )}
    </div>
  );
}

export default App;
