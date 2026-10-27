import { Info } from 'lucide-react'

export default function WorkspaceNotice() {
  return (
    <div className="workspace-notice" role="status">
      <Info size={17} aria-hidden="true" />
      <span><strong>Frontend preview</strong> — patient, case, and image upload records use connected APIs. Reports are not integrated; AI analysis is unavailable.</span>
    </div>
  )
}
