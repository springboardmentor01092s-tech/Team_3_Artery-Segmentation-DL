import type { LucideIcon } from 'lucide-react'
import { ArrowUpRight } from 'lucide-react'

export default function MetricCard({ icon: Icon, label, value, tint }: {
  icon: LucideIcon
  label: string
  value: string
  tint: 'blue' | 'green' | 'red' | 'violet'
}) {
  return (
    <article className={`metric-card metric-card--${tint}`}>
      <span className="metric-card__icon"><Icon size={22} strokeWidth={2.2} aria-hidden="true" /></span>
      <div className="metric-card__copy"><strong>{value}</strong><span>{label}</span></div>
      <ArrowUpRight className="metric-card__arrow" size={18} aria-hidden="true" />
    </article>
  )
}
