import { useEffect, useState } from 'react'
import { Header } from './components/header/Header'
import { WhatsAppLayout } from './components/layouts/WhatsAppLayout'
import { LiveDashboardLayout } from './components/layouts/LiveDashboardLayout'
import { deriveGlobalNotification, useSimulationStore } from './lib/simulationStore'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell } from 'lucide-react'

export function App() {
  const [, setTick] = useState(0)
  const { checkBackendConnection, subscribeToEvents, disconnectEventStream, source, systemState } = useSimulationStore()
  const globalNotification = deriveGlobalNotification(systemState.events)

  useEffect(() => {
    void checkBackendConnection()
    subscribeToEvents()

    return () => {
      disconnectEventStream()
    }
  }, [checkBackendConnection, subscribeToEvents, disconnectEventStream])

  useEffect(() => {
    const id = window.setInterval(() => setTick((value) => value + 1), 500)
    return () => window.clearInterval(id)
  }, [])

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#16162a_0%,#0a0a0b_40%,#070708_100%)] text-text relative overflow-x-hidden">
      <Header />

      {/* Global Notification Toast */}
      <AnimatePresence>
        {globalNotification && (
          <motion.div
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className="fixed top-20 left-1/2 z-50 flex items-center gap-2 bg-[#121218] border border-[#00a884]/40 px-4 py-2 rounded-full shadow-[0_10px_30px_rgba(0,168,132,0.2)]"
          >
            <Bell size={14} className="text-[#00a884] animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-widest text-[#00a884]">{globalNotification}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="p-3 2xl:container 2xl:mx-auto h-[calc(100vh-64px)] relative">
        <AnimatePresence mode="wait">
          {source === 'whatsapp' ? (
             <WhatsAppLayout key="whatsapp" />
          ) : (
             <LiveDashboardLayout key="live" />
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}
