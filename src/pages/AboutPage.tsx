import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'

export default function AboutPage() {
  return (
    <div className="about-page">
      <header className="login-header">
        <PublicHeader />
      </header>
      <main className="about-main">
        <article className="about-card">
          <p className="page-eyebrow">ABOUT THE PROJECT</p>
          <h1>CoronAI</h1>
          <p>
            CoronAI is a research-oriented web application developed to organize coronary angiography images and support experimental artery segmentation, stenosis detection, localization, severity assessment, visualization and reporting using deep learning techniques.
          </p>
          <p>
            It provides a workspace for managing patients, cases and medical images, reviewing available analysis outputs and generating reports.
          </p>
          <p className="about-prototype-note">
            This is an AI-assisted research and decision-support prototype, not an autonomous diagnostic system. Its outputs should be clinically verified.
          </p>
          <Link className="about-back-link" to="/login"><ArrowLeft size={16} aria-hidden="true" />Back to Login</Link>
        </article>
      </main>
      <footer className="login-footer">
        <span>© 2026 CoronAI</span>
      </footer>
    </div>
  )
}
