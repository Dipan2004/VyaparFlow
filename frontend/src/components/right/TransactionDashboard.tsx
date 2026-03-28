import { CreditCard, Receipt } from 'lucide-react'
import { deriveInvoices, useSimulationStore } from '../../lib/simulationStore'

function formatRupees(amount: number) {
  return `Rs. ${amount.toLocaleString()}`
}

export function TransactionDashboard() {
  const { systemState, confirmPayment, confirmingInvoiceId, state } = useSimulationStore()
  const invoices = deriveInvoices(systemState.events)
  const totalOrders = invoices.length
  const totalPending = invoices
    .filter((invoice) => invoice.status !== 'paid')
    .reduce((sum, invoice) => sum + Number(invoice.total || invoice.total_amount || 0), 0)
  const totalPaid = invoices
    .filter((invoice) => invoice.status === 'paid')
    .reduce((sum, invoice) => sum + Number(invoice.total || invoice.total_amount || 0), 0)

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-md border border-[#d9dce3] bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-[#e7e9ee] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-[#1f2937]">Business Dashboard</h2>
          <p className="text-xs text-[#6b7280]">Live invoice and payment state from backend events</p>
        </div>
        <span
          className={
            state === 'processing'
              ? 'rounded-full bg-[#eff6ff] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#1d4ed8]'
              : 'rounded-full bg-[#ecfdf5] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#047857]'
          }
        >
          {state === 'processing' ? 'Processing' : 'Live'}
        </span>
      </div>

      <div className="grid gap-3 border-b border-[#e7e9ee] bg-[#f8fafc] p-4 md:grid-cols-2">
        <div className="rounded-md border border-[#d9dce3] bg-white p-3">
          <div className="mb-2 flex items-center gap-2 text-[#1f2937]">
            <Receipt size={16} />
            <span className="text-xs font-semibold uppercase tracking-[0.2em]">Invoices</span>
          </div>
          <p className="text-2xl font-semibold text-[#111827]">{totalOrders}</p>
          <p className="text-xs text-[#6b7280]">Created through the live order pipeline</p>
        </div>

        <div className="rounded-md border border-[#d9dce3] bg-white p-3">
          <div className="mb-2 flex items-center gap-2 text-[#1f2937]">
            <CreditCard size={16} />
            <span className="text-xs font-semibold uppercase tracking-[0.2em]">Payment Ledger</span>
          </div>
          <div className="flex items-center justify-between text-sm text-[#111827]">
            <span>Paid</span>
            <span className="font-semibold">{formatRupees(totalPaid)}</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-sm text-[#111827]">
            <span>Pending</span>
            <span className="font-semibold">{formatRupees(totalPending)}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <div className="overflow-hidden rounded-md border border-[#d9dce3]">
          <table className="min-w-full divide-y divide-[#e7e9ee] text-sm">
            <thead className="bg-[#f8fafc]">
              <tr className="text-left text-xs uppercase tracking-[0.2em] text-[#6b7280]">
                <th className="px-4 py-3">Invoice ID</th>
                <th className="px-4 py-3">Item Name</th>
                <th className="px-4 py-3">Quantity</th>
                <th className="px-4 py-3">Price</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e7e9ee] bg-white">
              {invoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-sm text-[#6b7280]">
                    No live invoice available yet.
                  </td>
                </tr>
              ) : (
                invoices.map((invoice) => {
                  const item = invoice.items?.[0]
                  const invoiceId = invoice.invoice_id
                  const isPaying = confirmingInvoiceId === invoiceId

                  return (
                    <tr key={invoiceId} className="text-[#111827]">
                      <td className="px-4 py-3 font-mono text-xs">{invoiceId}</td>
                      <td className="px-4 py-3">{item?.name || invoice.item || 'Unknown item'}</td>
                      <td className="px-4 py-3">{item?.qty ?? invoice.quantity ?? 0}</td>
                      <td className="px-4 py-3">{formatRupees(Number(item?.price || invoice.unit_price || 0))}</td>
                      <td className="px-4 py-3 font-semibold">
                        {formatRupees(Number(invoice.total || invoice.total_amount || 0))}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={
                            invoice.status === 'paid'
                              ? 'rounded bg-[#dcfce7] px-2 py-1 text-xs font-semibold uppercase text-[#166534]'
                              : 'rounded bg-[#fef3c7] px-2 py-1 text-xs font-semibold uppercase text-[#92400e]'
                          }
                        >
                          {invoice.status === 'paid' ? 'Paid' : 'Pending'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {invoice.status === 'paid' ? (
                          <span className="text-xs font-medium text-[#64748b]">Settled</span>
                        ) : (
                          <button
                            onClick={() => void confirmPayment(invoiceId)}
                            disabled={isPaying}
                            className="rounded-md bg-[#0f766e] px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#115e59] disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isPaying ? 'Paying...' : 'Pay Now'}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
