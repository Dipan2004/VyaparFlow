import { Header } from './components/header/Header'
import { WhatsAppSim } from './components/left/WhatsAppSim'
import { AgentPanel } from './components/center/AgentPanel'
import { TransactionPanel } from './components/right/TransactionPanel'

export function App() {
  return (
    <div className="h-screen flex flex-col bg-bg text-text overflow-hidden">
      <Header />

      {/* Main grid */}
      <main className="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        {/* Left panel — Chat */}
        <section className="col-span-3 flex flex-col min-h-0">
          <WhatsAppSim />
        </section>

        {/* Center — Agent Pipeline */}
        <section className="col-span-5 flex flex-col min-h-0">
          <AgentPanel />
        </section>

        {/* Right — Transaction */}
        <section className="col-span-4 flex flex-col min-h-0">
          <TransactionPanel />
        </section>
      </main>
    </div>
  )
}
