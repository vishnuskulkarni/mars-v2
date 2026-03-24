import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download, BookOpen, Database, Lightbulb, Shield, Layers, Search, FlaskConical, FileOutput, Map } from 'lucide-react';
import { fetchReport, getExportUrl } from '../utils/api';

const TABS = [
  { key: 'output', label: 'Full Report', icon: FileOutput },
  { key: 'opportunity_map', label: 'Opportunity Map', icon: Map },
  { key: 'literature', label: 'Literature', icon: BookOpen },
  { key: 'data', label: 'Data & Plots', icon: Database },
  { key: 'hypothesis', label: 'Hypotheses', icon: Lightbulb },
  { key: 'methods', label: 'Methods', icon: FlaskConical },
  { key: 'scout', label: 'Discovered Papers', icon: Search },
  { key: 'critique', label: 'Critique', icon: Shield },
];

export default function ReportView({ sessionId }) {
  const [report, setReport] = useState(null);
  const [activeTab, setActiveTab] = useState('output');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (sessionId) {
      setLoading(true);
      fetchReport(sessionId)
        .then(setReport)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-16 text-text-secondary">
        Failed to load report.
      </div>
    );
  }

  // Determine content for each tab
  let activeContent;
  if (activeTab === 'output') {
    // Full report from Output agent, fall back to synthesis
    activeContent = report.agents?.output?.output || report.synthesis || 'No report available.';
    // Try to extract just Section 1 (before Opportunity Map)
    const section2Idx = activeContent.indexOf('## SECTION 2');
    if (section2Idx > 0) {
      activeContent = activeContent.slice(0, section2Idx).trim();
    }
  } else if (activeTab === 'opportunity_map') {
    const fullOutput = report.agents?.output?.output || '';
    const section2Idx = fullOutput.indexOf('## SECTION 2');
    activeContent = section2Idx > 0
      ? fullOutput.slice(section2Idx).trim()
      : 'No opportunity map available.';
  } else {
    activeContent = report.agents?.[activeTab]?.output || 'No output available.';
  }

  // Custom renderer to handle plot images
  const imgRenderer = ({ src, alt, ...props }) => {
    // Plot images from the API need proper handling
    return (
      <img
        src={src}
        alt={alt || ''}
        className="max-w-full rounded-lg border border-border my-4"
        loading="lazy"
        {...props}
      />
    );
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm text-text-secondary mb-1">Research Report</p>
          <p className="text-lg font-medium">{report.research_question}</p>
        </div>
        <a
          href={getExportUrl(sessionId)}
          download
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm text-text-secondary hover:text-text-primary hover:border-accent transition-colors"
        >
          <Download size={16} />
          Download
        </a>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-surface rounded-lg border border-border overflow-x-auto">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
              activeTab === key
                ? 'bg-accent/10 text-accent'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-surface border border-border rounded-xl p-8 report-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{ img: imgRenderer }}
        >
          {activeContent}
        </ReactMarkdown>
      </div>
    </div>
  );
}
