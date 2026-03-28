import { useEffect, useRef } from 'react'
import { useSimulationStore } from '../../lib/simulationStore'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { Microscope, Database, ShieldCheck, Receipt, CreditCard, BookText, BrainCircuit } from 'lucide-react'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

const AGENT_ICONS: Record<string, React.ElementType> = {
  intent: Microscope,
  extraction: Database,
  validation: ShieldCheck,
  invoice: Receipt,
  payment: CreditCard,
  ledger: BookText,
  autonomy: BrainCircuit,
}

export function AgentGraph() {
  const { agentSteps, state } = useSimulationStore()
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to active node
  useEffect(() => {
    if (state === 'processing' && scrollContainerRef.current) {
      const activeElement = scrollContainerRef.current.querySelector('[data-active="true"]')
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
      }
    }
  }, [agentSteps, state])

  return (
    <div className="flex flex-col bg-[#0d0d12] rounded-md border border-divider/40 p-3 shrink-0 relative overflow-hidden h-auto">
      <div className="flex items-center justify-between mb-4 border-b border-divider/20 pb-2">
        <h2 className="text-[10px] font-bold text-text-muted uppercase tracking-[0.2em] flex items-center gap-1.5 px-1">
          <BrainCircuit size={11} className="text-blue-500" />
          Pipeline Execution
        </h2>
        
        <div className="flex gap-4 items-center px-1">
          <div className="flex gap-1.5 items-center">
             <div className="w-1.5 h-1.5 rounded-full bg-divider/40"></div> 
             <span className="text-[8px] font-bold uppercase tracking-widest text-text-muted/60">Ready</span>
          </div>
          <div className="flex gap-1.5 items-center">
             <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-[pulse_1s_infinite]"></div> 
             <span className="text-[8px] font-bold uppercase tracking-widest text-blue-500">Active</span>
          </div>
          <div className="flex gap-1.5 items-center">
             <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div> 
             <span className="text-[8px] font-bold uppercase tracking-widest text-emerald-500">Done</span>
          </div>
        </div>
      </div>

      <div 
        ref={scrollContainerRef}
        className="flex-1 flex items-center overflow-x-auto overflow-y-hidden pb-4 pt-2 -mx-2 px-2 custom-scrollbar snap-x snap-mandatory"
      >
        <div className="flex flex-nowrap items-center min-w-max">
          {agentSteps.map((step, index) => {
            const Icon = AGENT_ICONS[step.key] || Microscope
            const isLast = index === agentSteps.length - 1
            const isRunning = step.status === 'running'
            const isDone = step.status === 'done'
            const isFailed = step.status === 'failed'

            let stateColor = 'bg-[#121218] border-divider/40 text-text-muted/40 opacity-40'
            let iconColor = 'text-text-muted/30'

            if (isRunning) {
              stateColor = 'bg-blue-500/10 border-blue-500/60 text-blue-100 opacity-100 z-10 scale-105 shadow-lg shadow-blue-500/5'
              iconColor = 'text-blue-400'
            } else if (isDone) {
              stateColor = 'bg-emerald-500/5 border-emerald-500/40 text-emerald-100 opacity-100'
              iconColor = 'text-emerald-500'
            } else if (isFailed) {
              stateColor = 'bg-red-500/10 border-red-500/60 text-red-100 opacity-100'
              iconColor = 'text-red-500'
            }

            return (
              <div 
                key={step.id} 
                className="flex items-center relative z-10 snap-center shrink-0"
                data-active={isRunning}
              >
                <div className="flex flex-col items-center gap-1.5">
                   <motion.div
                     className={cn(
                       "flex items-center justify-center p-0 rounded-sm border transition-all duration-300",
                       stateColor,
                       "w-12 h-12 shrink-0 border-dashed"
                     )}
                   >
                     <Icon size={16} strokeWidth={2.5} className={cn("transition-colors duration-300", iconColor)} />
                   </motion.div>
                   <span className={cn(
                     "text-[8px] uppercase tracking-[1px] font-bold text-center",
                     isRunning ? "text-blue-400" : isDone ? "text-emerald-500" : isFailed ? "text-red-500" : "text-text-muted/40"
                   )}>
                      {step.key}
                   </span>
                </div>

                {!isLast && (
                  <div className="w-8 h-[1px] relative mx-2 shrink-0 self-center -mt-3.5">
                     <div className="absolute inset-0 bg-divider/30"></div>
                     {isDone && (
                        <div className="absolute top-0 left-0 bottom-0 bg-emerald-500/60" style={{ width: '100%' }} />
                     )}
                     {isRunning && (
                        <div className="absolute top-0 left-0 bottom-0 bg-blue-500 animate-pulse" style={{ width: '50%' }} />
                     )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
