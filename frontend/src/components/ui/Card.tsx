import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  glow?: 'primary' | 'success' | 'destructive' | 'warning' | null
}

export function Card({ children, className = '', glow = null }: CardProps) {
  const glowClass = glow
    ? glow === 'primary' ? 'glow-primary'
      : glow === 'success' ? 'glow-success'
      : glow === 'destructive' ? 'glow-destructive'
      : 'glow-warning'
    : ''

  return (
    <div
      className={`bg-card border border-border rounded-xl ${glowClass} ${className}`}
    >
      {children}
    </div>
  )
}
