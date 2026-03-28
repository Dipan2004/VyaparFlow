import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { deriveActivityLog, useSimulationStore } from '../../lib/simulationStore'

export function ActivityFeed() {
  const { systemState } = useSimulationStore()
  const activityLog = deriveActivityLog(systemState.logs)

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3">
        <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted">Agent Activity</span>
      </div>

      <Card className="min-h-[320px] flex-1 overflow-y-auto p-4">
        {activityLog.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            Activity entries will appear here.
          </div>
        ) : (
          <div className="space-y-3">
            {activityLog.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between gap-3 rounded-xl border border-border/60 p-3">
                <div className="flex items-center gap-2">
                  <Badge type={entry.type}>{entry.type}</Badge>
                  <span className="text-sm text-text">{entry.label}</span>
                </div>
                <span className="text-xs text-muted">
                  {entry.timestamp.toLocaleTimeString('en-US', { hour12: false })}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
