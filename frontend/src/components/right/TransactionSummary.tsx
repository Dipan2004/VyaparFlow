import { User, Package, Receipt, CreditCard, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { useSimulationStore } from '../../lib/simulationStore'

function TransactionField({ delay, visible, children }: { delay: number; visible: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`transition-all duration-300 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}
      style={{ transitionDelay: visible ? `${delay}ms` : '0ms' }}
    >
      {children}
    </div>
  )
}

export function TransactionSummary() {
  const { transaction, transactionField } = useSimulationStore()

  const showCustomer = transactionField === 'customer' || transactionField === null && !!transaction
  const showItems     = transactionField === 'items'     || transactionField === null && !!transaction
  const showAmount    = transactionField === 'amount'    || transactionField === null && !!transaction
  const showInvoice   = transactionField === 'invoice'   || transactionField === null && !!transaction
  const showPayment   = transactionField === 'payment'  || transactionField === null && !!transaction

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Transaction</span>
        {transaction && (
          <Badge type={transaction.paymentStatus === 'success' ? 'DONE' : transaction.paymentStatus === 'pending' ? 'RETRY' : 'FAIL'}>
            {transaction.paymentStatus}
          </Badge>
        )}
      </div>

      {/* Content */}
      <div className="flex-1">
        {!transaction ? (
          <Card className="h-full flex flex-col items-center justify-center min-h-[280px] border-dashed">
            <div className="w-12 h-12 rounded-xl border border-border flex items-center justify-center mb-3">
              <Receipt size={20} className="text-muted/50" />
            </div>
            <p className="text-[11px] text-muted text-center leading-relaxed max-w-[160px]">
              Transaction details will appear here as the pipeline runs
            </p>
          </Card>
        ) : (
          <Card className="space-y-4 p-4">
            {/* Customer */}
            <TransactionField delay={0} visible={showCustomer}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                  <User size={14} className="text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] text-muted uppercase tracking-wider">Customer</p>
                  <p className="text-[13px] font-semibold text-text truncate">{transaction.customer}</p>
                </div>
              </div>
            </TransactionField>

            {/* Divider */}
            {showItems && <div className="border-t border-border" />}

            {/* Items */}
            <TransactionField delay={400} visible={showItems}>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-warning/10 border border-warning/20 flex items-center justify-center shrink-0">
                  <Package size={14} className="text-warning" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] text-muted uppercase tracking-wider mb-1">Items</p>
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
            </TransactionField>

            {/* Divider */}
            {showAmount && <div className="border-t border-border" />}

            {/* Amount */}
            <TransactionField delay={700} visible={showAmount}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-success/10 border border-success/20 flex items-center justify-center shrink-0">
                  <CreditCard size={14} className="text-success" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] text-muted uppercase tracking-wider">Amount</p>
                  <p className="text-[18px] font-bold tracking-tight text-text">
                    ₹{transaction.amount.toLocaleString()}
                  </p>
                </div>
              </div>
            </TransactionField>

            {/* Divider */}
            {showInvoice && <div className="border-t border-border" />}

            {/* Invoice */}
            <TransactionField delay={1000} visible={showInvoice}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                  <Receipt size={14} className="text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] text-muted uppercase tracking-wider">Invoice</p>
                  <p className="text-[11px] font-mono text-text">{transaction.invoiceId}</p>
                  <p className="text-[10px] text-muted">Order: {transaction.orderId}</p>
                </div>
              </div>
            </TransactionField>

            {/* Divider */}
            {showPayment && <div className="border-t border-border" />}

            {/* Payment status */}
            <TransactionField delay={1300} visible={showPayment}>
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${
                  transaction.paymentStatus === 'success'
                    ? 'bg-success/10 border-success/20'
                    : transaction.paymentStatus === 'pending'
                    ? 'bg-warning/10 border-warning/20'
                    : 'bg-destructive/10 border-destructive/20'
                }`}>
                  {transaction.paymentStatus === 'success' ? (
                    <CheckCircle size={14} className="text-success" />
                  ) : transaction.paymentStatus === 'pending' ? (
                    <Clock size={14} className="text-warning" />
                  ) : (
                    <AlertCircle size={14} className="text-destructive" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] text-muted uppercase tracking-wider">Payment</p>
                  <p className={`text-[12px] font-semibold ${
                    transaction.paymentStatus === 'success'
                      ? 'text-success'
                      : transaction.paymentStatus === 'pending'
                      ? 'text-warning'
                      : 'text-destructive'
                  }`}>
                    {transaction.paymentStatus === 'success' ? 'Payment Received' :
                     transaction.paymentStatus === 'pending' ? 'Payment Pending' : 'Payment Failed'}
                  </p>
                </div>
              </div>
            </TransactionField>
          </Card>
        )}
      </div>
    </div>
  )
}
