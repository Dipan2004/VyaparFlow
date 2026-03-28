export type EntryType = 'PROCESS' | 'DONE' | 'FAIL' | 'RETRY' | 'WAIT'
export type Source = 'demo' | 'whatsapp'
export type BackendSource = 'whatsapp' | 'payment' | 'marketplace'
export type AgentStatus = 'idle' | 'pending' | 'running' | 'done' | 'failed'
export type SimState = 'idle' | 'simulating' | 'complete' | 'error'

export interface ActivityEntry {
  id: string
  type: EntryType
  label: string
  timestamp: Date
  active: boolean
  agent?: string
}

export interface ChatMessage {
  id: string
  text: string
  sender: 'user' | 'bot'
  status?: 'sent' | 'delivered' | 'read'
  timestamp: Date
  msgType?: 'USER INPUT' | 'SYSTEM RESPONSE' | 'INVOICE' | 'PAYMENT LOG'
}

export interface PhoneNotification {
  id: string
  type?: 'whatsapp' | 'system'
  title: string
  message: string
  timestamp: number
}

export interface BackendLog {
  id: string
  agent: string
  status: string
  action: string
  detail: string
  timestamp: string
}

export type BackendEventType =
  | 'log'
  | 'pipeline_step'
  | 'message_received'
  | 'intent_detected'
  | 'extraction_done'
  | 'validation_done'
  | 'routing_done'
  | 'execution_done'
  | 'invoice_generated'
  | 'payment_requested'
  | 'payment_completed'
  | 'error_occurred'
  | 'recovery_triggered'
  | 'recovery_success'

export interface BackendEvent {
  id: string
  event_id?: string
  sequence?: number
  sequence_number?: number
  type: BackendEventType
  timestamp: string
  agent?: string | null
  step?: string | null
  message?: string
  status?: string
  data?: Record<string, unknown>
  payload?: Record<string, unknown>
  log?: BackendLog | null
}

export interface AgentStep {
  id: string
  name: string
  key: string
  status: AgentStatus
  message: string
  timestamp: Date
}

export interface Alert {
  type: 'warning' | 'critical' | 'info'
  message: string
}

export interface RiskInfo {
  level?: 'low' | 'medium' | 'high'
  factors?: string[]
}

export interface CustomerSummary {
  name: string
}

export interface OrderSummary {
  item?: string
  quantity?: number
  status?: string
  source?: string
}

export interface PaymentSummary {
  invoice_id?: string
  amount?: number
  status?: 'paid' | 'pending'
}

export interface DecisionSummary {
  intent?: string
  priority?: 'low' | 'medium' | 'high' | 'critical' | 'normal'
  priority_score?: number
  risk?: RiskInfo['level']
}

export interface TransactionItem {
  name: string
  qty: number
}

export interface Transaction {
  customer: string
  items: TransactionItem[]
  amount: number
  invoiceId: string
  paymentStatus: 'pending' | 'success' | 'failed'
  orderId: string
  itemTotal: number
  paymentType?: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  priorityScore: number
  risk?: RiskInfo
  alerts?: Alert[]
  order?: OrderSummary
  payment?: PaymentSummary
  decision?: DecisionSummary
  invoice?: Invoice
}

export interface InvoiceItem {
  name?: string
  qty?: number
  price?: number
}

export interface Invoice {
  id: string
  invoice_id: string
  customer?: string
  items: InvoiceItem[]
  total: number
  total_amount?: number
  status: 'pending' | 'paid'
  order_id?: string
  item?: string
  quantity?: number
  unit_price?: number
  timestamp?: string
}

export interface ApiResponse {
  message: string
  intent: string
  intents: string[]
  data: Record<string, unknown>
  multi_data: Record<string, unknown>
  event: { event?: string; [key: string]: unknown }
  invoice?: Invoice | null
  events?: BackendEvent[]
  live_logs?: BackendLog[]
  history?: BackendLog[]
  customer?: CustomerSummary
  order?: OrderSummary
  payment?: PaymentSummary
  decision?: DecisionSummary
  source: string
  sheet_updated: boolean
  model: string
  priority: 'low' | 'medium' | 'high' | 'critical' | 'normal'
  priority_score: number
  risk?: RiskInfo
  alerts?: Alert[]
  verification?: Record<string, unknown>
  recovery?: Record<string, unknown>
  monitor?: Record<string, unknown>
  latency?: number
}

export interface DemoNotification {
  id: string
  appName: string
  source: BackendSource
  title: string
  message: string
  accentColor: string
  icon: string
}

export interface PaymentConfirmResponse {
  invoice: Invoice
  payment: PaymentSummary
  event: BackendEvent
}
