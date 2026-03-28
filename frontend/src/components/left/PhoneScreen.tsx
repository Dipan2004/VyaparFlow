import { useSimulationStore } from '../../lib/simulationStore'
import { NotificationOverlay } from './NotificationOverlay'
import { AnimatePresence } from 'framer-motion'
import { Signal, Wifi, Battery } from 'lucide-react'

export function PhoneScreen() {
  const { phoneNotifications } = useSimulationStore()
  const timeStr = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })

  return (
    <div className="flex h-full w-full items-center justify-center p-4 lg:p-8">
      <div 
        className="relative flex w-full max-w-[280px] shrink-0 flex-col overflow-hidden rounded-[2.5rem] border border-[#d9dce3] bg-[#111827] shadow-sm aspect-[9/19] sm:max-w-[320px] md:rounded-[3rem]"
      >
        <div className="z-20 flex shrink-0 items-center justify-between px-6 py-4 text-[11px] font-semibold text-white/90">
          <span>{timeStr}</span>
          <div className="flex items-center gap-1.5 opacity-80">
            <Signal size={12} />
            <Wifi size={12} />
            <Battery size={14} />
          </div>
        </div>

        <div className="relative z-10 flex w-full flex-1 flex-col gap-2 px-4 pt-2">
          <AnimatePresence>
            {phoneNotifications.map((notif) => (
              <NotificationOverlay key={notif.id} notification={notif} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
