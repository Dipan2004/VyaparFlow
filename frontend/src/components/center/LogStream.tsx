import { useEffect, useRef } from 'react'
import { Terminal, Activity } from 'lucide-react'
import { deriveActivityLog, useSimulationStore } from '../../lib/simulationStore'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

const AGENT_COLORS: Record<string, string> = {
  IntentAgent: 'text-blue-400 border-blue-400/30',
  ExtractionAgent: 'text-purple-400 border-purple-400/30',
  ValidationAgent: 'text-pink-400 border-pink-400/30',
  SkillRouterAgent: 'text-yellow-400 border-yellow-400/30',
  ExecutionAgent: 'text-emerald-400 border-emerald-400/30',
  LedgerAgent: 'text-emerald-400 border-emerald-400/30',
  RecoveryAgent: 'text-cyan-400 border-cyan-400/30',
  Orchestrator: 'text-orange-300 border-orange-300/30',
  PaymentAPI: 'text-emerald-300 border-emerald-300/30',
  System: 'text-red-400 border-red-400/50',
}

function padZero(num: number) {
  return num.toString().padStart(2, '0')
}

function formatTime(d: Date) {
  return `${padZero(d.getHours())}:${padZero(d.getMinutes())}:${padZero(d.getSeconds())}.${d.getMilliseconds().toString().padStart(3, '0')}`
}

export function LogStream() {
  const { systemState, state } = useSimulationStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const activityLog = deriveActivityLog(systemState.logs)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [activityLog])

  return (
    <div className="flex flex-col flex-1 bg-black/80 backdrop-blur-lg rounded-md border border-divider/40 shadow-inner relative overflow-hidden font-mono text-[10px]">
      <div className="bg-[#121218] border-b border-divider/40 py-1.5 px-3 flex items-center justify-between sticky top-0 z-10 shrink-0">
        <div className="flex items-center gap-1.5 text-text-muted">
          <Terminal size={10} className="text-text-muted opacity-80" />
          <span className="uppercase tracking-[0.2em] font-bold opacity-60">sys.log</span>
        </div>
        
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 uppercase tracking-widest text-text-muted">
             <Activity size={8} className={state === 'processing' ? 'animate-pulse text-blue-400' : 'opacity-30'} />
             <span>{activityLog.length}</span>
          </div>
        </div>
      </div>

      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin scrollbar-thumb-divider scrollbar-track-transparent custom-scrollbar leading-tight tracking-[0.02em]"
      >
        {activityLog.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-text-muted/30">
            <span>[WAITING_FOR_TRACE]</span>
          </div>
        ) : (
          activityLog.map((log) => {
             const agentKey = log.agent || 'System'
             const agentStyle = AGENT_COLORS[agentKey] || 'text-gray-400 border-gray-400/30'
              
             return (
               <div key={log.id} className="flex items-start gap-2 hover:bg-white/5 py-0.5 rounded-sm transition-colors group">
                 <span className="text-text-muted/30 whitespace-nowrap opacity-50">{formatTime(log.timestamp)}</span>
                 <span className={cn("whitespace-nowrap w-24 truncate", agentStyle.split(' ')[0])}>[{agentKey}]</span>
                 <div className="flex-1 break-words">
                    <span className={cn(
                       log.type === 'FAIL' ? 'text-red-400 font-bold bg-red-400/10 px-1' :
                       log.type === 'RETRY' ? 'text-orange-300 italic' :
                       log.type === 'DONE' ? 'text-emerald-300' :
                       log.type === 'WAIT' ? 'text-gray-500 italic' : 'text-text-muted group-hover:text-text/90 transition-colors'
                    )}>
                      {log.label}
                    </span>
                 </div>
               </div>
             )
          })
        )}
      </div>
    </div>
  )
}
