import type { ReactNode } from 'react'

export default function Panel({ title, description, action, className = '', children }: {
  title: string
  description?: string
  action?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel__heading">{description ? <div className="panel__title-group"><h2>{title}</h2><p className="panel__description">{description}</p></div> : <h2>{title}</h2>}{action}</div>
      {children}
    </section>
  )
}
