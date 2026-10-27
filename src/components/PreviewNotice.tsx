import { Info } from 'lucide-react'

export default function PreviewNotice() {
  return (
    <div className="preview-notice" role="status">
      <Info size={17} aria-hidden="true" />
      <span><strong>Frontend preview</strong> — case records are connected; patient management and AI analysis are not available in this preview.</span>
    </div>
  )
}
