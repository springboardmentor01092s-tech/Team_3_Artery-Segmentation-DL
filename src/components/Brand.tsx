import { HeartPulse } from 'lucide-react'

export default function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`brand ${compact ? 'brand--compact' : ''}`}>
      <span className="brand__mark"><HeartPulse aria-hidden="true" /></span>
      {!compact && <span className="brand__name">Artery Analysis System</span>}
    </span>
  )
}
