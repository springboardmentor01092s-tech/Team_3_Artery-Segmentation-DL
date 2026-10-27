import type { LucideIcon } from 'lucide-react'

export default function EmptyState({ icon: Icon, title, description }: {
  icon: LucideIcon
  title: string
  description: string
}) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><Icon size={21} aria-hidden="true" /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  )
}
