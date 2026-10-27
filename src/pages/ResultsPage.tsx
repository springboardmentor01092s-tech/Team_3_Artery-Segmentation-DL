import { useState } from 'react'
import { Activity, ArrowLeft, Download, FileImage, Image, Layers2, Ruler, ZoomIn, ZoomOut, Move, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import EmptyDataTable from '../components/EmptyDataTable'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'

const resultViews = ['Original image', 'Segmentation overlay', 'Stenosis detection'] as const

export default function ResultsPage() {
  const [activeView, setActiveView] = useState<(typeof resultViews)[number]>(resultViews[0])
  return (
    <div className="feature-page results-page">
      <WorkspaceNotice />
      <div className="results-heading-row">
        <PageHeader title="Analysis Results" description="Review image outputs and findings from a completed analysis run." eyebrow="ANALYSIS" />
        <Link className="button button--secondary button--small back-case-button" to="/cases"><ArrowLeft size={15} /> Back to cases</Link>
      </div>
      <div className="result-selectors">
        <label>Case<select disabled defaultValue=""><option value="">No case selected</option></select></label>
        <label>Image<select disabled defaultValue=""><option value="">No image available</option></select></label>
        <label>Analysis run<select disabled defaultValue=""><option value="">No analysis run available</option></select></label>
      </div>
      <div className="results-workspace">
        <Panel title="Images in case (0)" className="result-thumbnails-panel">
          <EmptyState icon={Image} title="No images available" description="Images will appear here after a case is selected." />
        </Panel>
        <Panel title="Image viewer" className="image-viewer-panel">
          <div className="viewer-tabs" role="tablist" aria-label="Result image view">
            {resultViews.map((view) => <button key={view} className={`viewer-tab ${activeView === view ? 'viewer-tab--active' : ''}`} type="button" role="tab" aria-selected={activeView === view} onClick={() => setActiveView(view)}>{view}</button>)}
          </div>
          <div className="viewer-stage"><div className="viewer-placeholder"><span><FileImage size={27} /></span><strong>{activeView} unavailable</strong><p>Select an image with a completed model run to view actual output.</p></div></div>
          <div className="viewer-toolbar" aria-label="Image viewer controls">
            <button type="button" disabled aria-label="Zoom in"><ZoomIn size={16} /></button><button type="button" disabled aria-label="Zoom out"><ZoomOut size={16} /></button><button type="button" disabled aria-label="Pan"><Move size={16} /></button><button type="button" disabled aria-label="Reset view"><RotateCcw size={16} /></button><button type="button" disabled aria-label="Measure"><Ruler size={16} /></button>
          </div>
        </Panel>
        <div className="result-side-stack">
          <Panel title="Stenosis findings"><EmptyState icon={Activity} title="No findings available" description="No analysis run is connected. No stenosis measurements are shown." /></Panel>
          <Panel title="Segmentation metrics"><EmptyState icon={Layers2} title="Metrics unavailable" description="Evaluation metrics require real model output and ground-truth data." /></Panel>
          <Panel title="Case information"><EmptyState icon={FileImage} title="No case selected" description="Case and analysis metadata will appear here." /></Panel>
        </div>
      </div>
      <div className="results-lower-grid">
        <Panel title="Segmentation outputs" className="result-outputs-panel"><EmptyState icon={Layers2} title="No segmentation artifacts" description="Masks and overlays will appear after a real analysis run." /></Panel>
        <Panel title="Download and export" className="result-export-panel">
          <button className="button button--primary export-button" type="button" disabled><Download size={15} /> Download report (PDF)</button>
          <button className="button button--secondary export-button" type="button" disabled><Download size={15} /> Download results (JSON)</button>
          <button className="button button--secondary export-button" type="button" disabled><Download size={15} /> Download measurements (CSV)</button>
        </Panel>
        <Panel title="Compare analysis runs" className="compare-panel">
          <label>Analysis run<select disabled defaultValue=""><option value="">No runs available</option></select></label>
          <button className="button button--secondary export-button" type="button" disabled>Compare runs</button>
        </Panel>
      </div>
      <Panel title="Stenosis findings" className="findings-table-panel">
        <EmptyDataTable columns={['Location', 'Minimum diameter', 'Reference diameter', 'Narrowing', 'Severity', 'Confidence']} icon={Activity} title="No findings to display" description="Findings will be listed only when returned by a connected model run." />
      </Panel>
    </div>
  )
}
