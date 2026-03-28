import { useState, useRef, useEffect } from 'react'
import { Send, User } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { deriveChatMessages, useSimulationStore } from '../../lib/simulationStore'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

export function WhatsAppLayout() {
  const [input, setInput] = useState('')
  const { sendChatMessage, isBotTyping, state, systemState, confirmPayment } = useSimulationStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatMessages = deriveChatMessages(systemState.events)
  const showPayButton = systemState.payment?.status === 'pending' && Number(systemState.payment?.amount || systemState.invoice?.total || 0) > 0

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, isBotTyping])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || state === 'simulating') return
    void sendChatMessage(input)
    setInput('')
  }
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col w-full max-w-2xl mx-auto h-[min(800px,calc(100vh-140px))] bg-[#EFEAE2] rounded-xl shadow-[0_0_50px_rgba(0,0,0,0.5)] overflow-hidden border border-white/10"
    >
      {/* WhatsApp Header */}
      <div className="bg-[#008069] p-3 sm:p-4 flex items-center gap-3 shadow-md z-10 shrink-0">
         <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center text-white shrink-0">
           <User size={20} />
         </div>
         <div className="flex flex-col">
           <span className="text-white font-medium text-[15px]">Vyapar Store Agent</span>
           {isBotTyping ? (
             <span className="text-white/80 text-xs">typing...</span>
           ) : (
             <span className="text-white/80 text-xs flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-400 rounded-full"></span> online
             </span>
           )}
         </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[url('https://i.pinimg.com/originals/8c/98/99/8c98994518b575bfd8c949e91d20548b.jpg')] bg-cover bg-center custom-scrollbar">
        <AnimatePresence>
          {chatMessages.map((msg) => {
             const isUser = msg.sender === 'user'

             return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className={cn(
                  "flex flex-col max-w-[85%] relative",
                  isUser ? "self-end items-end ml-auto" : "self-start items-start mr-auto"
                )}
              >
                <div className={cn(
                  "px-3.5 py-2 text-[15px] leading-snug shadow-sm max-w-full break-words whitespace-pre-line",
                  isUser
                    ? "bg-[#d9fdd3] text-[#111b21] rounded-l-xl rounded-br-sm rounded-tr-xl" 
                    : "bg-white text-[#111b21] rounded-r-xl rounded-bl-sm rounded-tl-xl"
                )}>
                  {msg.text}
                </div>
              </motion.div>
            )
          })}

          {showPayButton && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="self-start"
            >
              <button
                onClick={() => void confirmPayment()}
                className="rounded-xl bg-[#00a884] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#008f6f]"
              >
                PAY NOW
              </button>
            </motion.div>
          )}

          {isBotTyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white text-[#111b21] self-start mr-auto rounded-r-xl rounded-bl-sm rounded-tl-xl px-4 py-3 text-xs flex items-center gap-2 w-fit shadow-sm"
            >
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} className="h-1" />
      </div>

      {/* Input Area */}
      <div className="bg-[#f0f2f5] p-3 flex gap-2 items-center shrink-0 border-t border-black/5">
         <form onSubmit={handleSubmit} className="flex gap-2 w-full">
           <input
             type="text"
             value={input}
             onChange={(e) => setInput(e.target.value)}
             disabled={state === 'simulating'}
             placeholder="Type a message"
             className="flex-1 bg-white border-none rounded-full px-4 py-2.5 text-[15px] text-[#111b21] focus:outline-none disabled:opacity-50 transition-all placeholder:text-[#667781] shadow-sm"
           />
           <button
             type="submit"
             disabled={!input.trim() || state === 'simulating'}
             className="bg-[#00a884] text-white p-2.5 rounded-full disabled:opacity-50 hover:bg-[#008f6f] transition-all shadow-sm shrink-0 flex items-center justify-center"
           >
             <Send size={20} className="translate-x-[1px]" />
           </button>
         </form>
      </div>
    </motion.div>
  )
}
