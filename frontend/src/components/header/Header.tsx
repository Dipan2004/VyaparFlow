import { Zap } from 'lucide-react'
import { useSimulationStore } from '../../lib/simulationStore'
import { SOURCE_COLORS, SOURCE_LABELS } from '../../lib/constants'
import type { Source } from '../../types'

export function Header() {
  const { source, setSource, scenario, generateMessage, runSimulation, state, isConnected } = useSimulationStore()

  const accentColor = SOURCE_COLORS[source]

  const handleGenerate = () => {
    if (!scenario) {
      generateMessage()
      setTimeout(() => runSimulation(), 60)
    } else {
      runSimulation()
    }
  }

  return (
    <header className="h-16 flex items-center justify-between px-6 border-b border-border bg-bg/80 backdrop-blur-sm shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
          <Zap size={16} className="text-primary" />
        </div>
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold tracking-tighter text-text">VyaparFlow</span>
            <span className="text-[10px] text-muted font-medium">AI Operations</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            {isConnected ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-[10px] text-muted">Backend connected</span>
              </>
            ) : (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-destructive" />
                <span className="text-[10px] text-muted">Offline</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Source selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center bg-card border border-border rounded-lg p-0.5 gap-0.5">
          {(['whatsapp', 'payment', 'marketplace'] as Source[]).map(s => {
            const active = source === s
            const color = SOURCE_COLORS[s]
            return (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={`relative z-10 flex items-center gap-1.5 py-1.5 px-3 rounded-md text-[11px] font-medium transition-all duration-150 cursor-pointer ${
                  active ? 'text-white' : 'text-muted hover:text-text'
                }`}
              >
                {active && (
                  <span
                    className="absolute inset-0 rounded-md opacity-80"
                    style={{ backgroundColor: color }}
                  />
                )}
                <span className="relative z-10 flex items-center gap-1.5">
                  {active && (
                    <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-pulse" />
                  )}
                  {SOURCE_LABELS[s]}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {scenario && state !== 'simulating' && (
          <span className="text-[11px] text-muted italic max-w-[200px] truncate">
            "{scenario}"
          </span>
        )}

        <button
          onClick={handleGenerate}
          disabled={state === 'simulating'}
          className="relative flex items-center gap-2 h-9 px-5 rounded-lg text-[11px] font-semibold tracking-wide transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed overflow-hidden"
          style={{ backgroundColor: state === 'simulating' ? undefined : accentColor }}
        >
          {state === 'simulating' ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-ping" />
              Processing...
            </>
          ) : (
            'Generate'
          )}
        </button>
      </div>
    </header>
  )
}
