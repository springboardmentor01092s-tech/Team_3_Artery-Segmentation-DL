import type { ReactNode } from 'react'

export default function PageHeader({ title, description, action, eyebrow = 'WORKSPACE' }: {
  title: string
  description: string
  action?: ReactNode
  eyebrow?: string
}) {
  return (
    <div className="page-heading feature-page-heading">
      <div><div className="eyebrow page-eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
      {action && <div className="page-heading__actions">{action}</div>}
    </div>
  )
}
