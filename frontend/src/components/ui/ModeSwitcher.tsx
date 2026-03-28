import { LayoutDashboard, MessageCircle } from 'lucide-react'
import { useSimulationStore } from '../../lib/simulationStore'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

export function ModeSwitcher() {
  const { source, setSource } = useSimulationStore()

  return (
    <div className="flex rounded-xl border border-divider/50 bg-surface/80 p-1 shadow-inner backdrop-blur-md">
      <button
        onClick={() => setSource('demo')}
        className={cn(
          'flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold uppercase tracking-widest transition-all',
          source === 'demo'
            ? 'bg-accent text-white'
            : 'text-text-muted hover:bg-white/5 hover:text-text',
        )}
      >
        <LayoutDashboard size={14} />
        Dashboard
      </button>

      <button
        onClick={() => setSource('whatsapp')}
        className={cn(
          'flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold uppercase tracking-widest transition-all',
          source === 'whatsapp'
            ? 'border border-accent/40 bg-accent-light/20 text-accent'
            : 'text-text-muted hover:bg-white/5 hover:text-text',
        )}
      >
        <MessageCircle size={14} />
        WhatsApp
      </button>
    </div>
  )
}
