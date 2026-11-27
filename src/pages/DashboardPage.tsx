import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, Clock3, FileText, FolderClosed, Image, Plus, Search, Upload, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import MetricCard from '../components/MetricCard'
import Panel from '../components/Panel'
import { apiRequest } from '../auth/api'
import { loadDashboardData } from '../features/dashboard/dashboard-data.mjs'
import type { DashboardData } from '../features/dashboard/dashboard-data.mjs'

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function formatTimestamp(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function statusBackground(counts: DashboardData['statusCounts']) {
  const total = counts.completed + counts.in_progress + counts.failed + counts.pending
  if (!total) return 'conic-gradient(#dce4ed 0 100%)'
  const completed = counts.completed / total * 100
  const active = completed + counts.in_progress / total * 100
  const failed = active + counts.failed / total * 100
  return `conic-gradient(#40b487 0 ${completed}%, #3788e7 ${completed}% ${active}%, #f27783 ${active}% ${failed}%, #a8b2bf ${failed}% 100%)`
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [activityFilter, setActivityFilter] = useState<'all' | 'analysis' | 'upload'>('all')
  const [caseSearch, setCaseSearch] = useState('')

  const load = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const dashboard = await loadDashboardData(apiRequest)
      setData(dashboard)
    } catch (cause) {
      setData(null)
      setError(cause instanceof Error ? cause.message : 'Unable to load dashboard records.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const summary = data?.summary
  const statusCounts = data?.statusCounts
  const visibleActivity = useMemo(() => (data?.recentActivity ?? []).filter((item) => (
    activityFilter === 'all' || (activityFilter === 'analysis' ? item.kind === 'analysis' : item.kind === 'image')
  )), [activityFilter, data?.recentActivity])
  const visibleRecentCases = useMemo(() => {
    const query = caseSearch.trim().toLocaleLowerCase()
    return (data?.recentCases ?? []).filter((record) => (
      !query || `${record.case_ref} ${record.patient_ref}`.toLocaleLowerCase().includes(query)
    ))
  }, [caseSearch, data?.recentCases])
  const metricValue = (value: number | undefined) => isLoading || error || value === undefined ? '—' : String(value)
  const sectionMessage = useMemo(() => isLoading
    ? <div className="dashboard-state-message" role="status">Loading authenticated workspace records…</div>
    : error
      ? <div className="dashboard-state-message dashboard-state-message--error" role="alert">Dashboard data is unavailable. Use Retry above to reload.</div>
      : null, [error, isLoading])

  return (
    <div className="dashboard-page dashboard-page--stitch">
      <div className="dashboard-summary">
        <header className="dashboard-intro">
          <div>
            <p className="dashboard-intro__eyebrow">CoronAI</p>
            <h1>Research Overview</h1>
            <p>Monitor registered cases, uploaded angiogram images, and saved analysis runs.</p>
          </div>
        </header>
        {error && <div className="dashboard-error" role="alert"><span>{error}</span><button className="button button--secondary button--small" type="button" onClick={() => void load()} disabled={isLoading}>Retry</button></div>}
        <section className="metric-grid" aria-label="Workspace summary" aria-busy={isLoading}>
          <MetricCard icon={FolderClosed} label="Total cases" value={metricValue(summary?.cases)} tint="blue" />
          <MetricCard icon={Image} label="Images uploaded" value={metricValue(summary?.images)} tint="teal" />
          <MetricCard icon={Workflow} label="Analyses completed" value={metricValue(summary?.analysesCompleted)} tint="indigo" />
          <MetricCard icon={Clock3} label="Analyses in progress" value={metricValue(summary?.analysesInProgress)} tint="violet" />
        </section>
      </div>
      <section className="dashboard-grid dashboard-grid--top">
        <Panel title="Analysis status" description="Case completion breakdown" className="status-panel">
          {sectionMessage ?? (statusCounts && <>
            <div className="empty-chart-wrap">
              <div className="donut-chart" style={{ background: statusBackground(statusCounts) }}><div><strong>{data?.summary.cases ?? 0}</strong><span>Cases</span></div></div>
              <ul className="chart-legend">
                <li><span className="legend-dot legend-dot--green" /> Completed <strong>{statusCounts.completed}</strong></li>
                <li><span className="legend-dot legend-dot--blue" /> In progress <strong>{statusCounts.in_progress}</strong></li>
                <li><span className="legend-dot legend-dot--red" /> Failed <strong>{statusCounts.failed}</strong></li>
                <li><span className="legend-dot legend-dot--gray" /> Pending <strong>{statusCounts.pending}</strong></li>
              </ul>
            </div>
            <p className="panel-footnote">Each case is counted once; completed status takes precedence.</p>
          </>)}
        </Panel>
        <Panel title="Recent activity" description="Latest pipeline events" action={<div className="dashboard-activity-filters" role="group" aria-label="Filter recent activity">
          {([
            ['all', 'All'], ['analysis', 'Analyses'], ['upload', 'Uploads'],
          ] as const).map(([filter, label]) => <button key={filter} type="button" aria-pressed={activityFilter === filter} className={activityFilter === filter ? 'dashboard-activity-filter dashboard-activity-filter--active' : 'dashboard-activity-filter'} onClick={() => setActivityFilter(filter)}>{label}</button>)}
        </div>} className="activity-panel">
          <div className="dashboard-panel-scroll dashboard-panel-scroll--activity">
            {sectionMessage ?? (visibleActivity.length ? <ul className="dashboard-activity-list">{visibleActivity.map((item) => <li key={item.id}>
              <span className={`dashboard-activity-icon dashboard-activity-icon--${item.kind}`}>{item.kind === 'image' ? <Image size={14} /> : item.kind === 'analysis' ? <Activity size={14} /> : <FolderClosed size={14} />}</span>
              <span className="dashboard-list-copy"><strong>{item.title}</strong><small>{item.detail}</small></span>
              <time dateTime={item.created_at}>{formatTimestamp(item.created_at)}</time>
            </li>)}</ul> : <EmptyState icon={Activity} title={activityFilter === 'analysis' ? 'No analyses yet' : activityFilter === 'upload' ? 'No uploads yet' : 'No activity yet'} description={activityFilter === 'all' ? 'Case, image, and analysis activity will appear here when records exist.' : 'Matching saved activity will appear here when records exist.'} />)}
          </div>
          <div className="dashboard-activity-panel-footer"><Link className="link-button" to="/cases">View all <ArrowRight size={14} /></Link></div>
        </Panel>
        <Panel title="Quick actions" description="Launch research workflows" className="quick-panel">
          <Link className="quick-action quick-action--primary" to="/cases?action=create"><span><Plus size={17} /> Create new case</span><ArrowRight size={15} /></Link>
          <Link className="quick-action" to="/upload"><span><Upload size={17} /> Upload images</span><ArrowRight size={15} /></Link>
          <Link className="quick-action" to="/upload"><span><Activity size={17} /> Start analysis</span><ArrowRight size={15} /></Link>
          <Link className="quick-action" to="/reports"><span><FileText size={17} /> View reports</span><ArrowRight size={15} /></Link>
        </Panel>
      </section>
      <section className="dashboard-grid dashboard-grid--bottom">
        <Panel title="Recent cases" action={<div className="dashboard-panel-actions">
          <label className="dashboard-case-search"><Search size={14} aria-hidden="true" /><input type="search" aria-label="Search recent cases" placeholder="Search cases…" value={caseSearch} onChange={(event) => setCaseSearch(event.target.value)} /></label>
          <Link className="link-button" to="/cases">View all <ArrowRight size={14} /></Link>
        </div>} className="cases-panel">
          <div className="dashboard-panel-scroll dashboard-panel-scroll--records">
            {sectionMessage ?? (visibleRecentCases.length ? <ul className="dashboard-record-list">{visibleRecentCases.map((record) => <li key={record.id}>
              <span className="dashboard-record-icon"><FolderClosed size={15} aria-hidden="true" /></span>
              <span className="dashboard-list-copy"><strong>{record.case_ref}</strong><small>{record.patient_ref}</small></span>
              <time dateTime={record.created_at}>{formatDate(record.created_at)}</time>
            </li>)}</ul> : <EmptyState icon={FolderClosed} title={data?.recentCases.length ? 'No matching cases' : 'No cases created'} description={data?.recentCases.length ? 'Try a different case or patient reference.' : 'Create a case to begin organizing patient images.'} />)}
          </div>
        </Panel>
        <Panel title="Recent analyses" description="Latest saved runs" action={<Link className="link-button" to="/results">View all <ArrowRight size={14} /></Link>} className="analyses-panel">
          <div className="dashboard-panel-scroll dashboard-panel-scroll--records">
            {sectionMessage ?? (data?.recentAnalyses.length ? <ul className="dashboard-record-list dashboard-analysis-list">{data.recentAnalyses.map((run) => <li key={run.id}>
              <span className="dashboard-record-icon dashboard-record-icon--analysis"><Workflow size={15} aria-hidden="true" /></span>
              <span className="dashboard-list-copy"><strong><Link to={`/results?${new URLSearchParams({ run_id: run.id }).toString()}`}>{run.case_ref}</Link></strong><small>{run.image_id ? `Image ${run.image_id.slice(0, 8)}` : 'Image unavailable'}</small></span>
              <span className={`dashboard-run-status dashboard-run-status--${run.status}`}>{run.status.replaceAll('_', ' ')}</span>
            </li>)}</ul> : <EmptyState icon={Activity} title="No analyses yet" description="Persisted analysis runs will appear here." />)}
          </div>
        </Panel>
      </section>
    </div>
  )
}
