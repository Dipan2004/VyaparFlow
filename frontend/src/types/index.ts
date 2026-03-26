export type EntryType = 'PROCESS' | 'DONE' | 'FAIL' | 'RETRY' | 'WAIT'
export type Source = 'whatsapp' | 'payment' | 'marketplace'
export type AgentStatus = 'pending' | 'running' | 'done' | 'failed'
export type SimState = 'idle' | 'simulating' | 'complete' | 'error'

// ─── Chat ───────────────────────────────────────────────────────────────────────
export interface ChatMessage {
  id: string
  text: string
  sender: 'user' | 'bot'
  status?: 'sent' | 'delivered' | 'read'
  timestamp: Date
}

// ─── Agent Steps (timeline) ────────────────────────────────────────────────────
export interface AgentStep {
  id: string
  name: string          // e.g. "IntentAgent"
  key: string           // e.g. "intent"
  status: AgentStatus
  message: string        // e.g. "Intent detected: order"
  timestamp: Date
}

// ─── Transaction / API Response ────────────────────────────────────────────────
export interface Transaction {
  customer: string
  items: { name: string; qty: number }[]
  amount: number
  invoiceId: string
  paymentStatus: 'pending' | 'success' | 'failed'
  orderId: string
  itemTotal: number
  paymentType?: string
}

export interface RiskInfo {
  level: 'low' | 'medium' | 'high'
  factors: string[]
}

export interface Alert {
  type: 'warning' | 'critical' | 'info'
  message: string
}

export interface ApiResponse {
  message: string
  intent: string
  intents: string[]
  data: Record<string, unknown>
  multi_data: Record<string, unknown>
  event: { event: string; [key: string]: unknown }
  source: string
  sheet_updated: boolean
  model: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  priority_score: number
  risk: RiskInfo
  alerts: Alert[]
  verification: Record<string, unknown>
  recovery: Record<string, unknown>
  monitor: Record<string, unknown>
}
