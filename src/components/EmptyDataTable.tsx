import type { LucideIcon } from 'lucide-react'
import EmptyState from './EmptyState'

export default function EmptyDataTable({ columns, icon, title, description }: {
  columns: string[]
  icon: LucideIcon
  title: string
  description: string
}) {
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody><tr><td colSpan={columns.length}><EmptyState icon={icon} title={title} description={description} /></td></tr></tbody>
      </table>
    </div>
  )
}
