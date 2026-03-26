import { useEffect, useRef } from 'react'
import { Send } from 'lucide-react'
import { Card } from '../ui/Card'
import { TypingDots, StatusTicks } from '../Animations'
import { useSimulationStore } from '../../lib/simulationStore'
import { SOURCE_COLORS } from '../../lib/constants'
import type { Source } from '../../types'

export function WhatsAppSim() {
  const {
    source,
    chatMessages,
    isBotTyping,
    sendChatMessage,
    currentMessage,
  } = useSimulationStore()

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const accentColor = SOURCE_COLORS[source as Source] || SOURCE_COLORS.whatsapp

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, isBotTyping])

  const handleSend = () => {
    const msg = currentMessage?.trim()
    if (!msg) return
    sendChatMessage(msg)
    useSimulationStore.getState().resetSimulation()
    useSimulationStore.setState({ currentMessage: '' })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    useSimulationStore.getState().setCurrentMessage?.(e.target.value)
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Chat</span>
        </div>
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium"
          style={{ backgroundColor: `${accentColor}20`, color: accentColor }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accentColor }} />
          {source === 'whatsapp' ? 'WhatsApp' : source === 'payment' ? 'Payment App' : 'Marketplace'}
        </div>
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden p-0 min-h-0">
        {/* Chat header */}
        <div
          className="flex items-center gap-2 px-4 py-3 border-b"
          style={{ borderColor: `${accentColor}30`, backgroundColor: `${accentColor}08` }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${accentColor}20` }}
          >
            <span className="text-[10px] font-bold" style={{ color: accentColor }}>V</span>
          </div>
          <div>
            <div className="text-[11px] font-semibold text-text">VyaparFlow Bot</div>
            <div className="text-[10px] text-success flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-success animate-pulse" />
              Online
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
          {chatMessages.length === 0 && !isBotTyping && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div
                className="w-12 h-12 rounded-2xl border flex items-center justify-center mb-3"
                style={{ borderColor: `${accentColor}30`, backgroundColor: `${accentColor}10` }}
              >
                <Send size={18} style={{ color: accentColor }} />
              </div>
              <p className="text-[11px] text-muted leading-relaxed px-4">
                Select a source and click <strong className="text-text">Generate</strong> to start
              </p>
            </div>
          )}

          {chatMessages.map(msg => (
            <div
              key={msg.id}
              className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-fade-up`}
            >
              <div
                className={`max-w-[82%] px-3 py-2 rounded-2xl text-[11px] leading-relaxed ${
                  msg.sender === 'user'
                    ? 'text-white rounded-br-sm'
                    : 'bg-card border border-border text-text rounded-bl-sm'
                }`}
                style={msg.sender === 'user' ? { backgroundColor: accentColor } : {}}
              >
                <p>{msg.text}</p>
                {msg.sender === 'user' && msg.status && (
                  <div className="flex justify-end mt-1">
                    <StatusTicks status={msg.status} />
                  </div>
                )}
                {msg.sender === 'bot' && (
                  <div className="text-[10px] mt-1" style={{ color: `${accentColor}CC` }}>
                    VyaparFlow
                  </div>
                )}
              </div>
            </div>
          ))}

          {isBotTyping && (
            <div className="flex justify-start animate-fade-up">
              <div className="bg-card border border-border rounded-2xl rounded-bl-sm px-4 py-3">
                <TypingDots />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-3 border-t border-border flex items-center gap-2">
          <input
            ref={inputRef}
            value={currentMessage || ''}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="flex-1 bg-bg border border-border rounded-full px-4 py-2 text-[11px] text-text placeholder:text-muted/50 focus:outline-none focus:border-border/80 transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={!(currentMessage?.trim())}
            className="w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-95 disabled:opacity-40 cursor-pointer"
            style={{ backgroundColor: accentColor }}
          >
            <Send size={14} className="text-white" />
          </button>
        </div>
      </Card>
    </div>
  )
}
