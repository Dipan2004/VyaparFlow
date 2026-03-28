import { Zap } from 'lucide-react'
import { useSimulationStore } from '../../lib/simulationStore'
import { ModeSwitcher } from '../ui/ModeSwitcher'

export function Header() {
  const { isConnected } = useSimulationStore()

  return (
    <header className="flex h-16 items-center justify-between border-b border-white/5 bg-black/20 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 shadow-[0_0_30px_rgba(109,99,255,0.18)]">
          <Zap size={16} className="text-primary" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-semibold tracking-tight text-text">VyaparFlow</span>
            <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-success' : 'bg-destructive'}`} />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <ModeSwitcher />
      </div>
      <div className="text-xs font-semibold uppercase tracking-[0.24em] text-text-muted">Backend Driven</div>
    </header>
  )
}
