import type { ReactNode } from 'react'
import type { EntryType } from '../../types'

interface BadgeProps {
  type: EntryType
  children: ReactNode
  className?: string
}

const styles: Record<EntryType, string> = {
  PROCESS: 'bg-primary/10 text-primary border-primary/20',
  DONE:    'bg-success/10 text-success border-success/20',
  FAIL:    'bg-destructive/10 text-destructive border-destructive/20',
  RETRY:   'bg-warning/10 text-warning border-warning/20',
  WAIT:    'bg-muted/10 text-muted border-border',
}

export function Badge({ type, children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wider border uppercase ${styles[type]} ${className}`}
    >
      {children}
    </span>
  )
}
