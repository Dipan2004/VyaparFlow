import { User, Package, Receipt, CreditCard, AlertTriangle, Zap, CheckCircle, Clock, XCircle, ShieldCheck } from 'lucide-react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { useSimulationStore } from '../../lib/simulationStore'

const PRIORITY_COLORS = {
  low:      { bg: 'bg-muted/10',   text: 'text-muted',   border: 'border-muted/20' },
  medium:   { bg: 'bg-warning/10',  text: 'text-warning',  border: 'border-warning/20' },
  high:     { bg: 'bg-destructive/10', text: 'text-destructive', border: 'border-destructive/20' },
  critical: { bg: 'bg-destructive/20', text: 'text-destructive', border: 'border-destructive/30' },
}

const RISK_COLORS = {
  low:    { bg: 'bg-success/10',  text: 'text-success',  border: 'border-success/20' },
  medium: { bg: 'bg-warning/10',   text: 'text-warning',   border: 'border-warning/20' },
  high:   { bg: 'bg-destructive/10', text: 'text-destructive', border: 'border-destructive/20' },
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-[10px] text-muted uppercase tracking-wider font-semibold mb-1">{children}</p>
}

export function TransactionPanel() {
  const { transaction, state, setTransaction } = useSimulationStore()

  const handleConfirmPayment = () => {
    if (!transaction) return
    setTransaction({
      ...transaction,
      paymentStatus: 'success',
    })
  }

  const handleMarkComplete = () => {
    useSimulationStore.getState().resetSimulation()
  }

  if (!transaction) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Transaction</span>
        </div>
        <Card className="h-full flex flex-col items-center justify-center min-h-[300px] border-dashed">
          <div className="w-12 h-12 rounded-xl border border-border flex items-center justify-center mb-3">
            <Receipt size={20} className="text-muted/50" />
          </div>
          <p className="text-[11px] text-muted text-center leading-relaxed max-w-[160px]">
            Transaction details will appear here after processing
          </p>
        </Card>
      </div>
    )
  }

  const pStyle = PRIORITY_COLORS[transaction.priority] || PRIORITY_COLORS.low
  const rStyle = RISK_COLORS[transaction.risk?.level || 'low'] || RISK_COLORS.low

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Transaction</span>
        <Badge
          type={transaction.paymentStatus === 'success' ? 'DONE' : transaction.paymentStatus === 'failed' ? 'FAIL' : 'RETRY'}
        >
          {transaction.paymentStatus}
        </Badge>
      </div>

      {/* Main card */}
      <Card className="space-y-4 p-4 flex-1 overflow-y-auto min-h-0">
        {/* Invoice ID + timestamp */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wider">Invoice</p>
            <p className="text-[12px] font-mono font-semibold text-text">{transaction.invoiceId}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-muted uppercase tracking-wider">Order</p>
            <p className="text-[11px] font-mono text-muted">{transaction.orderId}</p>
          </div>
        </div>

        <div className="border-t border-border" />

        {/* Customer */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
            <User size={14} className="text-primary" />
          </div>
          <div className="min-w-0">
            <SectionLabel>Customer</SectionLabel>
            <p className="text-[13px] font-semibold text-text">{transaction.customer}</p>
          </div>
        </div>

        {/* Items */}
        {transaction.items.length > 0 && (
          <>
            <div className="border-t border-border" />
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-warning/10 border border-warning/20 flex items-center justify-center shrink-0">
                <Package size={14} className="text-warning" />
              </div>
              <div className="min-w-0 flex-1">
                <SectionLabel>Items</SectionLabel>
                <div className="space-y-1">
                  {transaction.items.map((item, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-[11px] text-text">{item.name}</span>
                      <span className="text-[10px] text-muted">×{item.qty}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Amount */}
        <div className="border-t border-border" />
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-success/10 border border-success/20 flex items-center justify-center shrink-0">
            <CreditCard size={14} className="text-success" />
          </div>
          <div className="min-w-0">
            <SectionLabel>Amount</SectionLabel>
            <p className="text-[20px] font-bold tracking-tight text-text">
              ₹{transaction.amount.toLocaleString()}
            </p>
          </div>
        </div>

        {/* Payment type */}
        {transaction.paymentType && transaction.paymentType !== 'unknown' && (
          <>
            <div className="border-t border-border" />
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-muted">Payment via</span>
              <span className="text-[11px] font-medium text-text capitalize">{transaction.paymentType}</span>
            </div>
          </>
        )}

        {/* AI Analysis */}
        <div className="border-t border-border" />

        {/* Priority */}
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${pStyle.bg}`}>
            <Zap size={14} className={pStyle.text} />
          </div>
          <div className="min-w-0 flex-1">
            <SectionLabel>Priority</SectionLabel>
            <div className="flex items-center gap-2">
              <span className={`text-[12px] font-bold uppercase ${pStyle.text}`}>{transaction.priority}</span>
              <span className="text-[10px] text-muted">score: {transaction.priorityScore}</span>
            </div>
          </div>
        </div>

        {/* Risk */}
        {transaction.risk && (
          <>
            <div className="border-t border-border" />
            <div className="flex items-start gap-3">
              <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${rStyle.bg}`}>
                <ShieldCheck size={14} className={rStyle.text} />
              </div>
              <div className="min-w-0 flex-1">
                <SectionLabel>Risk Level</SectionLabel>
                <span className={`text-[12px] font-bold uppercase ${rStyle.text}`}>
                  {transaction.risk.level}
                </span>
                {transaction.risk.factors && transaction.risk.factors.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {transaction.risk.factors.map((f, i) => (
                      <p key={i} className="text-[10px] text-muted">• {f}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* Alerts */}
        {transaction.alerts && transaction.alerts.length > 0 && (
          <>
            <div className="border-t border-border" />
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center justify-center shrink-0">
                <AlertTriangle size={14} className="text-destructive" />
              </div>
              <div className="min-w-0 flex-1">
                <SectionLabel>Alerts ({transaction.alerts.length})</SectionLabel>
                <div className="space-y-1">
                  {transaction.alerts.map((alert, i) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <span className={`text-[10px] mt-0.5 ${
                        alert.type === 'critical' ? 'text-destructive' :
                        alert.type === 'warning' ? 'text-warning' : 'text-primary'
                      }`}>•</span>
                      <span className="text-[11px] text-muted">{alert.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Actions */}
        {state === 'complete' && (
          <>
            <div className="border-t border-border" />
            <div className="flex gap-2">
              {transaction.paymentStatus !== 'success' && (
                <button
                  onClick={handleConfirmPayment}
                  className="flex-1 py-2 rounded-lg bg-success/10 border border-success/20 text-success text-[11px] font-semibold hover:bg-success/20 transition-colors cursor-pointer"
                >
                  Confirm Payment
                </button>
              )}
              <button
                onClick={handleMarkComplete}
                className="flex-1 py-2 rounded-lg bg-card border border-border text-muted text-[11px] font-semibold hover:bg-card/80 transition-colors cursor-pointer"
              >
                Reset
              </button>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
