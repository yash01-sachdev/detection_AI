import type { ReactNode } from 'react'

type PanelProps = {
  title: string
  subtitle?: string
  children: ReactNode
}

export function Panel({ title, subtitle, children }: PanelProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}
