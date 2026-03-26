export function TypingDots({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <span className="typing-dot w-1.5 h-1.5 rounded-full bg-muted" style={{ animationDelay: '0ms' }} />
      <span className="typing-dot w-1.5 h-1.5 rounded-full bg-muted" style={{ animationDelay: '200ms' }} />
      <span className="typing-dot w-1.5 h-1.5 rounded-full bg-muted" style={{ animationDelay: '400ms' }} />
    </div>
  )
}

export function StatusTicks({ status }: { status: 'sent' | 'delivered' | 'read' }) {
  const color = status === 'read' ? 'text-primary' : status === 'delivered' ? 'text-muted' : 'text-muted'
  const ticks = status === 'sent' ? '✓' : status === 'delivered' ? '✓✓' : '✓✓'
  return <span className={`text-[10px] ${color}`}>{ticks}</span>
}

interface DotProps {
  type: 'PROCESS' | 'DONE' | 'FAIL' | 'RETRY'
  active?: boolean
}

export function GlowDot({ type, active = false }: DotProps) {
  const colors = {
    PROCESS: 'bg-primary',
    DONE:    'bg-success',
    FAIL:    'bg-destructive',
    RETRY:   'bg-warning',
  }
  const glows = {
    PROCESS: 'dot-glow-primary',
    DONE:    'dot-glow-success',
    FAIL:    'dot-glow-destructive',
    RETRY:   'dot-glow-warning',
  }
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${colors[type]} ${active ? glows[type] : ''} ${active ? 'animate-pulse-glow' : ''}`}
      style={{ color: 'currentColor' }}
    />
  )
}
