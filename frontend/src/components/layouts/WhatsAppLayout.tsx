import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CreditCard, Receipt, Send, User } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { deriveChatMessages, useSimulationStore } from '../../lib/simulationStore'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ChatMessage, Invoice } from '../../types'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

function formatCurrency(amount?: number) {
  return `Rs. ${Number(amount || 0).toLocaleString()}`
}

function getPrimaryItem(invoice?: Invoice | null) {
  return invoice?.items?.[0]
}

export function WhatsAppLayout() {
  const [input, setInput] = useState('')
  const {
    sendChatMessage,
    isSubmittingMessage,
    state,
    systemState,
    confirmPayment,
    confirmingInvoiceId,
  } = useSimulationStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatMessages = deriveChatMessages(systemState.events)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, state, confirmingInvoiceId])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isSubmittingMessage || state === 'processing') return
    void sendChatMessage(input)
    setInput('')
  }

  const renderInvoiceCard = (message: ChatMessage) => {
    const invoice = message.invoice
    if (!invoice) return null

    const item = getPrimaryItem(invoice)

    return (
      <div className="w-full min-w-[280px] max-w-[360px] overflow-hidden rounded-2xl border border-[#d7e9df] bg-white shadow-[0_12px_30px_rgba(17,27,33,0.08)]">
        <div className="flex items-center justify-between border-b border-[#eef2f5] bg-[#f6fbf8] px-4 py-3">
          <div className="flex items-center gap-2 text-[#0f5132]">
            <Receipt size={16} />
            <span className="text-xs font-semibold uppercase tracking-[0.18em]">Invoice</span>
          </div>
          <span
            className={cn(
              'rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]',
              invoice.status === 'paid'
                ? 'bg-[#dcfce7] text-[#166534]'
                : 'bg-[#fef3c7] text-[#92400e]',
            )}
          >
            {invoice.status === 'paid' ? 'Paid' : 'Pending'}
          </span>
        </div>

        <div className="space-y-4 px-4 py-4 text-[#111b21]">
          <div className="grid gap-3 rounded-xl bg-[#f8fafc] p-3">
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-medium text-[#667781]">Invoice ID</span>
              <span className="font-mono text-xs font-semibold">{invoice.invoice_id}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-medium text-[#667781]">Item Name</span>
              <span className="text-sm font-semibold">{item?.name || invoice.item || 'Unknown item'}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-medium text-[#667781]">Quantity</span>
              <span className="text-sm font-semibold">{item?.qty ?? invoice.quantity ?? 0}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-medium text-[#667781]">Price</span>
              <span className="text-sm font-semibold">{formatCurrency(item?.price ?? invoice.unit_price)}</span>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-xl bg-[#111b21] px-4 py-3 text-white">
            <span className="text-xs uppercase tracking-[0.18em] text-white/70">Total</span>
            <span className="text-lg font-semibold">{formatCurrency(invoice.total || invoice.total_amount)}</span>
          </div>
        </div>
      </div>
    )
  }

  const renderPaymentRequest = (message: ChatMessage) => {
    const invoice = message.invoice || systemState.invoice
    const payment = message.payment || systemState.payment
    const invoiceId = payment?.invoice_id || invoice?.invoice_id
    const isPaid = invoice?.status === 'paid' || payment?.status === 'paid'
    const isPaying = Boolean(invoiceId && confirmingInvoiceId === invoiceId)

    return (
      <div className="min-w-[280px] max-w-[360px] rounded-2xl border border-[#dce7f4] bg-[#f7fbff] px-4 py-4 text-[#111b21] shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
        <div className="flex items-center gap-2 text-[#0f4c81]">
          {isPaid ? <CheckCircle2 size={16} /> : <CreditCard size={16} />}
          <span className="text-xs font-semibold uppercase tracking-[0.18em]">
            {isPaid ? 'Payment Received' : 'Payment Request'}
          </span>
        </div>

        <p className="mt-3 text-sm leading-relaxed text-[#334155]">
          {message.text || 'Payment request received from backend.'}
        </p>

        <div className="mt-3 flex items-center justify-between rounded-xl bg-white px-3 py-3">
          <span className="text-xs font-medium text-[#64748b]">Amount</span>
          <span className="text-base font-semibold text-[#0f172a]">
            {formatCurrency(payment?.amount ?? invoice?.total ?? invoice?.total_amount)}
          </span>
        </div>

        {!isPaid && invoiceId && (
          <button
            onClick={() => void confirmPayment(invoiceId)}
            disabled={isPaying}
            className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-[#00a884] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#008f6f] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPaying ? 'Processing Payment...' : 'Pay Now'}
          </button>
        )}
      </div>
    )
  }

  const renderMessageContent = (message: ChatMessage) => {
    if (message.msgType === 'INVOICE') {
      return renderInvoiceCard(message)
    }

    if (message.msgType === 'PAYMENT REQUEST' || message.msgType === 'PAYMENT LOG') {
      return renderPaymentRequest(message)
    }

    return (
      <div
        className={cn(
          'px-3.5 py-2 text-[15px] leading-snug shadow-sm max-w-full break-words whitespace-pre-line',
          message.sender === 'user'
            ? 'bg-[#d9fdd3] text-[#111b21] rounded-l-xl rounded-br-sm rounded-tr-xl'
            : 'bg-white text-[#111b21] rounded-r-xl rounded-bl-sm rounded-tl-xl',
        )}
      >
        {message.text}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.25 }}
      className="flex flex-col w-full max-w-2xl mx-auto h-[min(800px,calc(100vh-140px))] overflow-hidden rounded-[28px] border border-white/10 bg-[#efeae2] shadow-[0_30px_80px_rgba(0,0,0,0.35)]"
    >
      <div className="bg-[#008069] p-3 sm:p-4 flex items-center gap-3 shadow-md z-10 shrink-0">
        <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center text-white shrink-0">
          <User size={20} />
        </div>
        <div className="flex flex-col">
          <span className="text-white font-medium text-[15px]">Vyapar Store Agent</span>
          <span className="text-white/80 text-xs flex items-center gap-1">
            <span
              className={cn(
                'w-1.5 h-1.5 rounded-full',
                state === 'processing' ? 'bg-[#fde047] animate-pulse' : 'bg-green-400',
              )}
            />
            {state === 'processing' ? 'processing backend events...' : 'online'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-[linear-gradient(180deg,#efeae2_0%,#e6dfd4_100%)] px-4 py-5 custom-scrollbar">
        <div className="flex flex-col gap-3">
          <AnimatePresence initial={false}>
            {chatMessages.map((message) => {
              const isUser = message.sender === 'user'

              return (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  className={cn(
                    'flex flex-col max-w-[88%] relative',
                    isUser ? 'self-end items-end ml-auto' : 'self-start items-start mr-auto',
                  )}
                >
                  {renderMessageContent(message)}
                </motion.div>
              )
            })}

            {chatMessages.length === 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-1 items-center justify-center py-12 text-center text-sm text-[#667781]"
              >
                Send a manual WhatsApp message to start the backend pipeline.
              </motion.div>
            )}

            {state === 'processing' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="self-start rounded-r-xl rounded-bl-sm rounded-tl-xl bg-white px-4 py-3 text-xs text-[#52656f] shadow-sm"
              >
                Backend is streaming live pipeline events...
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} className="h-1" />
        </div>
      </div>

      <div className="bg-[#f0f2f5] p-3 shrink-0 border-t border-black/5">
        <form onSubmit={handleSubmit} className="flex gap-2 items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a business message"
            className="flex-1 rounded-full bg-white px-4 py-2.5 text-[15px] text-[#111b21] shadow-sm outline-none placeholder:text-[#667781]"
          />
          <button
            type="submit"
            disabled={!input.trim() || isSubmittingMessage || state === 'processing'}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-[#00a884] text-white transition-colors hover:bg-[#008f6f] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send size={18} className="translate-x-[1px]" />
          </button>
        </form>
      </div>
    </motion.div>
  )
}
