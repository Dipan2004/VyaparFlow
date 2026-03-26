import { Badge } from '../ui/Badge'
import { GlowDot } from '../Animations'
import { useSimulationStore } from '../../lib/simulationStore'
import type { ActivityEntry } from '../../types'

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function ActivityItem({ entry, index }: { entry: ActivityEntry; index: number }) {
  return (
    <div
      className="flex items-start gap-3 py-2.5 px-3 rounded-lg hover:bg-card/40 transition-colors group animate-fade-up"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      {/* Glow dot */}
      <div className="mt-0.5 shrink-0">
        <GlowDot type={entry.type} active={entry.active} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge type={entry.type}>{entry.type}</Badge>
          <span className="text-[11px] text-text/90 font-medium leading-snug">
            {entry.label}
          </span>
        </div>
      </div>

      {/* Timestamp */}
      <span className="text-[10px] text-muted font-mono shrink-0 mt-0.5 group-hover:text-muted/70 transition-colors">
        {formatTime(entry.timestamp)}
      </span>
    </div>
  )
}

export function ActivityFeed() {
  const { activityLog, state } = useSimulationStore()
  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Agent Activity</span>
        </div>
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
          <span className="text-[10px] text-muted">{activityLog.length} steps</span>
        </div>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {activityLog.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 rounded-xl bg-card border border-border flex items-center justify-center mb-3">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted/60">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <p className="text-[11px] text-muted leading-relaxed max-w-[180px]">
              Agent activity will appear here when simulation starts
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {activityLog.map((entry, i) => (
              <ActivityItem key={entry.id} entry={entry} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
