import type { ReactNode } from 'react'

export default function Panel({ title, action, className = '', children }: {
  title: string
  action?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel__heading"><h2>{title}</h2>{action}</div>
      {children}
    </section>
  )
}
