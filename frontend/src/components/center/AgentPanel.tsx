import { useSimulationStore } from '../../lib/simulationStore'
import type { AgentStep, AgentStatus } from '../../types'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'

const AGENT_ICONS: Record<string, string> = {
  system: '⚙',
  intent: '🎯',
  extraction: '📋',
  validation: '✅',
  router: '🔀',
  ledger: '📒',
  verification: '🔍',
  monitor: '📡',
  prediction: '🔮',
  urgency: '⚡',
  escalation: '🚨',
  recovery: '🔄',
}

const STATUS_STYLES: Record<AgentStatus, { bg: string; text: string; dot: string; icon: string }> = {
  pending: { bg: 'bg-muted/10', text: 'text-muted', dot: 'bg-muted', icon: '○' },
  running: { bg: 'bg-primary/10', text: 'text-primary', dot: 'bg-primary animate-pulse', icon: '◉' },
  done:    { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success', icon: '✓' },
  failed:  { bg: 'bg-destructive/10', text: 'text-destructive', dot: 'bg-destructive', icon: '✗' },
}

function AgentTimelineItem({ step, isLast }: { step: AgentStep; isLast: boolean }) {
  const style = STATUS_STYLES[step.status]

  return (
    <div className="flex gap-3 relative">
      {/* Timeline connector */}
      {!isLast && (
        <div className="absolute left-[11px] top-8 bottom-0 w-px bg-border -translate-x-1/2" />
      )}

      {/* Status icon */}
      <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold z-10 ${style.bg} ${style.text}`}>
        {style.icon}
      </div>

      {/* Content */}
      <div className={`flex-1 pb-5 ${isLast ? 'pb-0' : ''}`}>
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className="text-[11px] font-semibold text-text">{step.name}</span>
          <Badge
            type={step.status === 'done' ? 'DONE' : step.status === 'running' ? 'PROCESS' : step.status === 'failed' ? 'FAIL' : 'RETRY'}
          >
            {step.status.toUpperCase()}
          </Badge>
        </div>
        <p className="text-[11px] text-muted leading-relaxed">{step.message}</p>
        <span className="text-[10px] text-muted/60 font-mono mt-1 block">
          {step.timestamp.toLocaleTimeString('en-US', { hour12: false })}
        </span>
      </div>
    </div>
  )
}

export function AgentPanel() {
  const { agentSteps, state } = useSimulationStore()

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Agent Pipeline</span>
        <div className="flex items-center gap-2">
          {state === 'simulating' && (
            <span className="flex items-center gap-1.5 text-[10px] text-primary">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
              Running
            </span>
          )}
          {state === 'complete' && (
            <span className="flex items-center gap-1.5 text-[10px] text-success">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              Complete
            </span>
          )}
          {state === 'error' && (
            <span className="flex items-center gap-1.5 text-[10px] text-destructive">
              <span className="w-1.5 h-1.5 rounded-full bg-destructive" />
              Error
            </span>
          )}
          <span className="text-[10px] text-muted">{agentSteps.length} steps</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {agentSteps.length === 0 ? (
          <Card className="h-full flex flex-col items-center justify-center min-h-[300px] border-dashed">
            <div className="w-12 h-12 rounded-xl bg-card border border-border flex items-center justify-center mb-3">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted/60">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <p className="text-[11px] text-muted text-center leading-relaxed max-w-[180px]">
              Click <strong className="text-text">Generate</strong> to run the agent pipeline
            </p>
          </Card>
        ) : (
          <div className="space-y-0.5">
            {agentSteps.map((step, i) => (
              <div key={step.id} className="animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                <AgentTimelineItem step={step} isLast={i === agentSteps.length - 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
