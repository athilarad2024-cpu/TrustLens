// pages/About.jsx
import { ShieldCheck, GitBranch, BookOpen, AlertTriangle } from 'lucide-react';

const modules = [
  { title: 'URL Phishing Detection', desc: 'Logistic Regression / Random Forest / XGBoost pipeline with 24 URL structural features and external security intelligence.', color: 'from-emerald-500 to-teal-600' },
  { title: 'Image AI Detection',     desc: 'EfficientNet-B0 fine-tuned classifier for AI-generated vs. real image classification with EXIF forensic signals.', color: 'from-violet-500 to-purple-600' },
  { title: 'Video Deepfake Detection', desc: 'Frame-level EfficientNet-B0 with face detection (Haar cascade) and multi-frame aggregation.', color: 'from-sky-500 to-blue-600' },
  { title: 'Trust Score Engine',     desc: 'Evidence-weighted 0–100 application-level score combining ML outputs, external intel, and technical signals.', color: 'from-amber-500 to-orange-600' },
  { title: 'Evidence & Explanation', desc: 'Rule-based + SHAP feature attributions translated into human-readable evidence items and numbered reasons.', color: 'from-rose-500 to-red-600' },
];

const stack = [
  ['Frontend',   'React 18, Vite, Tailwind CSS, Axios'],
  ['Backend',    'Python 3, FastAPI, Uvicorn, SQLAlchemy'],
  ['ML Models',  'PyTorch, EfficientNet-B0, scikit-learn, XGBoost'],
  ['Vision',     'OpenCV, Pillow, torchvision, timm'],
  ['Explainability', 'SHAP, rule-based engine'],
  ['Database',   'SQLite (default) / PostgreSQL'],
  ['External Intel', 'Google Safe Browsing v4, VirusTotal v3'],
];

export default function About() {
  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-16 space-y-16 animate-fade-in">
      {/* Hero */}
      <section className="text-center space-y-4">
        <div className="inline-flex w-20 h-20 rounded-3xl bg-gradient-to-br from-primary-500 to-accent
                        items-center justify-center shadow-2xl shadow-primary-900/40 mx-auto">
          <ShieldCheck size={36} className="text-white" />
        </div>
        <h1 className="text-4xl font-extrabold text-white">About TrustAI</h1>
        <p className="text-slate-400 leading-relaxed max-w-2xl mx-auto">
          TrustAI is an explainable, multimodal AI system for assessing the trustworthiness of digital content.
          It accepts images, videos, and website URLs, analyzes each using specialized machine-learning models,
          and produces a Trust Score, Risk Level, and evidence-based explanation.
        </p>
      </section>

      {/* Modules */}
      <section className="space-y-5">
        <h2 className="text-2xl font-bold text-white">System Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {modules.map(({ title, desc, color }) => (
            <div key={title} className="card p-5 space-y-2 hover:border-primary-700/50 transition-colors">
              <div className={`inline-block text-xs font-bold uppercase tracking-wide
                              bg-gradient-to-r ${color} bg-clip-text text-transparent`}>
                {title}
              </div>
              <p className="text-slate-400 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Stack */}
      <section className="space-y-5">
        <h2 className="text-2xl font-bold text-white">Technology Stack</h2>
        <div className="card divide-y divide-surface-border">
          {stack.map(([layer, tech]) => (
            <div key={layer} className="flex gap-6 px-5 py-3">
              <span className="text-primary-400 font-medium text-sm w-32 flex-shrink-0">{layer}</span>
              <span className="text-slate-300 text-sm">{tech}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <section className="card-glass p-6 space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-amber-400" />
          <h2 className="text-lg font-semibold text-amber-300">Important Limitations</h2>
        </div>
        <ul className="space-y-2 text-slate-400 text-sm">
          {[
            'TrustAI is a decision-support tool, not a universal truth oracle.',
            'AI detectors can produce false positives and false negatives.',
            'Trust Score is a probabilistic risk estimate, not factual proof.',
            'External API results depend on provider availability and API key configuration.',
            'Model performance depends entirely on the quality and coverage of training datasets.',
            'A clean reputation lookup does not prove a URL is universally safe.',
            'Missing EXIF metadata is not evidence of image manipulation.',
          ].map(lim => (
            <li key={lim} className="flex gap-2">
              <span className="text-amber-600 flex-shrink-0 mt-0.5">•</span>
              {lim}
            </li>
          ))}
        </ul>
      </section>

      {/* Links */}
      <section className="flex flex-wrap justify-center gap-4">
        <a href="https://github.com" target="_blank" rel="noreferrer" className="btn-secondary">
          <GitBranch size={16} /> Source Code
        </a>
        <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="btn-secondary">
          <BookOpen size={16} /> API Docs
        </a>
      </section>
    </main>
  );
}
