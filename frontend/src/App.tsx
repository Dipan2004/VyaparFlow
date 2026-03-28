import { useEffect } from 'react'
import { Header } from './components/header/Header'
import { WhatsAppLayout } from './components/layouts/WhatsAppLayout'
import { LiveDashboardLayout } from './components/layouts/LiveDashboardLayout'
import { useSimulationStore } from './lib/simulationStore'
import { AnimatePresence } from 'framer-motion'

export function App() {
  const { checkBackendConnection, subscribeToEvents, disconnectEventStream, source } = useSimulationStore()

  useEffect(() => {
    void checkBackendConnection()
    subscribeToEvents()

    return () => {
      disconnectEventStream()
    }
  }, [checkBackendConnection, subscribeToEvents, disconnectEventStream])

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#16162a_0%,#0a0a0b_40%,#070708_100%)] text-text relative overflow-x-hidden">
      <Header />

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
