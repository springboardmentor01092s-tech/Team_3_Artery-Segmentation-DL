import { useState } from 'react'
import { FileText, Download, Settings2 } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'

const reportTabs = ['Summary', 'Images', 'Findings', 'Measurements', 'Model & settings']
const reportSections = ['Patient and case information', 'Key findings summary', 'Annotated images', 'Segmentation results', 'Stenosis measurements', 'Evaluation metrics', 'Model and analysis settings']

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState(reportTabs[0])
  return (
    <div className="feature-page reports-page">
      <WorkspaceNotice />
      <PageHeader title="Report Generation" description="Preview and export a report for a saved analysis run." />
      <div className="report-selectors">
        <label>Patient reference<select disabled defaultValue=""><option value="">No patients available</option></select></label>
        <label>Case ID<select disabled defaultValue=""><option value="">No cases available</option></select></label>
        <label>Analysis run<select disabled defaultValue=""><option value="">No completed runs available</option></select></label>
      </div>
      <div className="report-layout">
        <div className="report-preview-column">
          <Panel title="Report preview" className="report-preview-panel">
            <div className="report-tabs" role="tablist" aria-label="Report preview sections">
              {reportTabs.map((tab) => <button key={tab} className={`report-tab ${activeTab === tab ? 'report-tab--active' : ''}`} type="button" role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}
            </div>
            <div className="report-paper">
              <div className="report-paper__header"><div className="report-paper__brand"><span><FileText size={19} /></span><div><strong>Artery Analysis Report</strong><small>Preview · no report generated</small></div></div><div className="report-paper__id">Report ID<br /><strong>—</strong></div></div>
              <div className="report-paper__body"><EmptyState icon={FileText} title={`${activeTab} not available`} description="Choose a completed analysis run to preview report content. No findings or measurements are fabricated." /></div>
            </div>
          </Panel>
        </div>
        <aside className="report-controls">
          <Panel title="Export report" className="export-report-panel">
            <p className="panel-description">Generate and download a report from an available analysis run.</p>
            <button className="export-format export-format--primary" type="button" disabled><FileText size={19} /><span><strong>Download PDF report</strong><small>Complete report with selected sections</small></span></button>
            <button className="export-format" type="button" disabled><Download size={19} /><span><strong>Download JSON</strong><small>Structured report data</small></span></button>
            <button className="export-format" type="button" disabled><Download size={19} /><span><strong>Download CSV</strong><small>Available measurements</small></span></button>
          </Panel>
          <Panel title="Report contents" className="report-contents-panel">
            {reportSections.map((section) => <label className="report-section-option" key={section}><input type="checkbox" disabled /> <span>{section}</span></label>)}
          </Panel>
          <Panel title="Report notes" className="report-notes-panel">
            <textarea disabled placeholder="Additional notes can be added when report generation is connected." />
          </Panel>
          <button className="button button--primary generate-report-button" type="button" disabled><FileText size={16} /> Generate report</button>
        </aside>
      </div>
      <div className="page-bottom-note"><Settings2 size={14} /> Reports can only be generated from saved outputs returned by a real model run.</div>
    </div>
  )
}
