import { motion } from 'framer-motion'
import { PhoneScreen } from '../left/PhoneScreen'
import { AgentGraph } from '../center/AgentGraph'
import { LogStream } from '../center/LogStream'
import { TransactionDashboard } from '../right/TransactionDashboard'

export function LiveDashboardLayout() {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      className="grid h-full grid-cols-1 gap-2 xl:grid-cols-12"
    >
      <section className="flex flex-col xl:col-span-3 min-h-[400px]">
        <PhoneScreen />
      </section>

      <section className="flex flex-col gap-2 xl:col-span-5 min-h-[400px]">
        <AgentGraph />
        <LogStream />
      </section>

      <section className="flex flex-col xl:col-span-4 min-h-[400px]">
        <TransactionDashboard />
      </section>
    </motion.div>
  )
}
