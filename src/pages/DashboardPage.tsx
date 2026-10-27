import { Activity, ArrowRight, Clock3, FileText, FolderClosed, Image, Plus, Upload, Workflow } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import MetricCard from '../components/MetricCard'
import Panel from '../components/Panel'
import PreviewNotice from '../components/PreviewNotice'
import { Link } from 'react-router-dom'

export default function DashboardPage() {
  return (
    <div className="dashboard-page">
      <PreviewNotice />
      <div className="page-heading">
        <div><div className="eyebrow page-eyebrow">OVERVIEW</div><h1>Dashboard</h1><p>Overview of cases, uploads, and analysis activity</p></div>
        <Link className="button button--primary button--small" to="/cases?action=create"><Plus size={16} aria-hidden="true" /> Create new case</Link>
      </div>
      <section className="metric-grid" aria-label="Workspace summary">
        <MetricCard icon={FolderClosed} label="Total cases" value="0" tint="blue" />
        <MetricCard icon={Image} label="Images uploaded" value="0" tint="green" />
        <MetricCard icon={Workflow} label="Analyses completed" value="0" tint="red" />
        <MetricCard icon={Clock3} label="Analyses in progress" value="0" tint="violet" />
      </section>
      <section className="dashboard-grid dashboard-grid--top">
        <Panel title="Analysis status" className="status-panel">
          <div className="empty-chart-wrap">
            <div className="donut-chart donut-chart--empty"><div><strong>0</strong><span>Cases</span></div></div>
            <ul className="chart-legend">
              <li><span className="legend-dot legend-dot--green" /> Completed <strong>0</strong></li>
              <li><span className="legend-dot legend-dot--blue" /> In progress <strong>0</strong></li>
              <li><span className="legend-dot legend-dot--red" /> Failed <strong>0</strong></li>
              <li><span className="legend-dot legend-dot--gray" /> Pending <strong>0</strong></li>
            </ul>
          </div>
          <p className="panel-footnote">Counts will appear when workspace records are connected.</p>
        </Panel>
        <Panel title="Recent activity" action={<button className="link-button" type="button">View all <ArrowRight size={14} /></button>} className="activity-panel">
          <EmptyState icon={Activity} title="No activity yet" description="Uploads and analysis activity will appear here." />
        </Panel>
        <Panel title="Quick actions" className="quick-panel">
          <Link className="quick-action quick-action--primary" to="/cases?action=create"><Plus size={17} /> Create new case</Link>
          <button className="quick-action" type="button" disabled title="Image upload will be available after the backend is connected."><Upload size={17} /> Upload images</button>
          <button className="quick-action" type="button" disabled title="AI analysis is unavailable until a real model is configured."><Activity size={17} /> Start analysis <span className="mini-status">Not configured</span></button>
          <button className="quick-action" type="button" disabled title="Reports will be available after the report workflow is implemented."><FileText size={17} /> View reports</button>
        </Panel>
      </section>
      <section className="dashboard-grid dashboard-grid--bottom">
        <Panel title="Recent cases" action={<Link className="link-button" to="/cases">View all <ArrowRight size={14} /></Link>} className="cases-panel">
          <div className="empty-table"><EmptyState icon={FolderClosed} title="No cases created" description="Create a case to begin organizing patient images." /></div>
        </Panel>
        <Panel title="Recent analyses" action={<span className="panel-subtitle">Last 7 days</span>} className="analyses-panel">
          <div className="bar-chart-empty" aria-label="No analysis activity to chart">
            <div className="bar-chart-empty__grid"><span /><span /><span /><span /></div>
            <div className="bar-chart-empty__message"><span className="bar-chart-empty__icon"><Activity size={18} /></span><strong>No analyses yet</strong><small>Activity will appear after real model runs are connected.</small></div>
            <div className="bar-chart-empty__labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
          </div>
        </Panel>
      </section>
      <div className="dashboard-footer-note"><span className="footer-note-dot" /> AI analysis is unavailable until a real model is configured. No predictions or measurements are shown.</div>
    </div>
  )
}
