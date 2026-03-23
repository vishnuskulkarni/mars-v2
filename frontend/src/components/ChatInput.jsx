import { useState } from 'react';
import { Send, FlaskConical } from 'lucide-react';
import FileUpload from './FileUpload';

export default function ChatInput({ onSubmit, isLoading }) {
  const [question, setQuestion] = useState('');
  const [litFiles, setLitFiles] = useState([]);
  const [dataFiles, setDataFiles] = useState([]);

  const canSubmit = question.trim().length > 0 && !isLoading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit(question.trim(), litFiles, dataFiles);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.metaKey && canSubmit) {
      handleSubmit();
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-65px)] px-4">
      <div className="w-full max-w-2xl">
        {/* Branding */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-3">
            <FlaskConical size={32} className="text-accent" />
            <h1 className="text-3xl font-bold tracking-tight">MARS</h1>
          </div>
          <p className="text-text-secondary">
            Multi-Agent Research System
          </p>
        </div>

        {/* Input card */}
        <div className="bg-surface border border-border rounded-xl p-6 space-y-5">
          {/* Research question */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              What's your research question?
            </label>
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g., How does sleep quality affect cognitive performance in college students?"
              rows={3}
              className="w-full bg-bg border border-border rounded-lg px-4 py-3 text-text-primary placeholder-text-secondary/50 resize-none focus:outline-none focus:border-accent transition-colors"
            />
            <div className="text-right mt-1">
              <span className="text-xs text-text-secondary">{question.length} chars</span>
            </div>
          </div>

          {/* File uploads */}
          <div className="grid grid-cols-2 gap-4">
            <FileUpload type="literature" files={litFiles} onFilesChange={setLitFiles} />
            <FileUpload type="data" files={dataFiles} onFilesChange={setDataFiles} />
          </div>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`w-full flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-all ${
              canSubmit
                ? 'bg-accent text-white hover:bg-accent/90 shadow-lg shadow-accent/20'
                : 'bg-border text-text-secondary cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Send size={18} />
            )}
            {isLoading ? 'Launching...' : 'Launch Analysis'}
          </button>
        </div>

        <p className="text-center text-xs text-text-secondary mt-4">
          Tip: Upload PDFs of relevant papers and CSV/Excel data files for the deepest analysis.
        </p>
      </div>
    </div>
  );
}
