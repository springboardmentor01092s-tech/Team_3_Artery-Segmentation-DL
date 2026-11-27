import { Info } from 'lucide-react'

export default function PreviewNotice() {
  return (
    <div className="preview-notice" role="status">
      <Info size={17} aria-hidden="true" />
      <span><strong>Application status</strong> — patient, case, image upload, and analysis workflows use connected backend services. Model outputs are not clinically validated; report generation is not integrated.</span>
    </div>
  )
}
