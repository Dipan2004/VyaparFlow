import { useEffect, useRef, useState } from 'react'
import { Send, Smartphone, MessageCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { deriveChatMessages } from '../../lib/simulationStore'
import { useSimulationStore } from '../../lib/simulationStore'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

export function ChatPanel() {
  const [input, setInput] = useState('')
  const { source, sendChatMessage, isBotTyping, state, systemState } = useSimulationStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Strictly backend-driven messages
  const chatMessages = deriveChatMessages(systemState.events)
  const isWhatsApp = source === 'whatsapp'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, isBotTyping])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isBotTyping || state === 'processing') return
    void sendChatMessage(input)
    setInput('')
  }

  return (
    <div className="flex h-full flex-col rounded-md border border-divider/40 bg-[#0a0a0c] relative font-sans shadow-inner overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-divider/40 bg-[#121218] px-4 py-2.5 shrink-0">
        <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-text/80">
          {isWhatsApp ? (
            <span className="flex items-center gap-2 text-[#00a884]">
              <MessageCircle size={12} strokeWidth={3} /> WhatsApp operational
            </span>
          ) : (
            <span className="flex items-center gap-2 text-text-muted">
              <Smartphone size={12} strokeWidth={3} /> Input Stream
            </span>
          )}
        </h3>
        {state === 'processing' && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm border border-blue-500/30 bg-blue-500/10">
             <span className="w-1 h-1 rounded-full bg-blue-400 animate-pulse"></span>
             <span className="text-[8px] font-bold uppercase tracking-widest text-blue-400">Processing</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-4 font-sans text-sm pb-8">
        <AnimatePresence initial={false}>
          {chatMessages.length === 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full flex-col items-center justify-center space-y-2 opacity-30">
               <span className="text-[10px] font-mono uppercase tracking-[0.3em]">[Awaiting Input]</span>
            </motion.div>
          )}

          {chatMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex max-w-[85%] flex-col gap-1",
                msg.sender === 'user' ? "self-end items-end" : "self-start items-start"
              )}
            >
              <div className={cn(
                'rounded-md px-3 py-2 text-[13px] leading-relaxed shadow-sm border border-white/5',
                msg.sender === 'user' 
                  ? 'bg-blue-600/20 text-blue-100 border-blue-500/20' 
                  : isWhatsApp ? 'bg-[#202c33] text-gray-100' : 'bg-surface text-text'
              )}>
                {msg.text || (msg.msgType === 'INVOICE' ? 'Invoice generated.' : 'Backend update received.')}
              </div>
              <span className="text-[9px] text-text-muted/40 font-mono px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </motion.div>
          ))}

          {isBotTyping && (
             <motion.div
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               className="self-start flex gap-1 items-center px-4 py-2"
             >
                <div className="flex gap-1">
                   <span className="w-1 h-1 rounded-full bg-text-muted/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                   <span className="w-1 h-1 rounded-full bg-text-muted/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                   <span className="w-1 h-1 rounded-full bg-text-muted/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
             </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-divider/40 bg-[#121218] p-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isWhatsApp ? "Send business command..." : "Type a message..."}
            className="flex-1 rounded-sm border border-divider/40 bg-black/40 px-3 py-2 text-xs font-medium text-text transition-all placeholder:text-text-muted/40 focus:border-white/20 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || isBotTyping || state === 'processing'}
            className="flex items-center justify-center rounded-sm bg-[#00a884] px-4 py-2 text-white transition-colors hover:bg-[#008f6f] disabled:opacity-40 shadow-sm"
          >
            <Send size={14} />
          </button>
        </form>
        <div className="mt-2 flex items-center justify-center gap-4 opacity-20 pointer-events-none">
           <span className="text-[8px] font-mono tracking-widest uppercase">E2E Encrypted</span>
           <span className="text-[8px] font-mono tracking-widest uppercase">NotiFlow v2.0</span>
        </div>
      </div>
    </div>
  )
}
