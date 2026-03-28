import { motion } from 'framer-motion'
import { MessageCircle, Settings } from 'lucide-react'
import type { PhoneNotification } from '../../types'

interface NotificationOverlayProps {
  notification: PhoneNotification
}

export function NotificationOverlay({ notification }: NotificationOverlayProps) {
  const isWhatsApp = notification.type === 'whatsapp'

  return (
    <motion.div
      initial={{ y: -80, opacity: 0, scale: 0.95 }}
      animate={{ y: 0, opacity: 1, scale: 1 }}
      exit={{ y: -40, opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="w-full bg-[#1e1e1e]/90 backdrop-blur-xl border border-white/10 rounded-2xl p-3 flex gap-3 items-start shadow-xl"
    >
      <div className={`mt-0.5 rounded-md p-1.5 shrink-0 ${isWhatsApp ? 'bg-[#25D366]/20' : 'bg-blue-500/20'}`}>
        {isWhatsApp ? (
           <MessageCircle size={16} className="text-[#25D366]" />
        ) : (
           <Settings size={16} className="text-blue-400" />
        )}
      </div>

      <div className="flex flex-col flex-1 overflow-hidden">
        <div className="flex items-center justify-between w-full">
           <span className="text-xs font-semibold text-white/90 truncate pr-2">
             {notification.title}
           </span>
           <span className="text-[10px] text-white/50 shrink-0">Now</span>
        </div>
        <span className="text-xs text-white/70 mt-0.5 leading-snug line-clamp-2">
          {notification.message}
        </span>
      </div>
    </motion.div>
  )
}
