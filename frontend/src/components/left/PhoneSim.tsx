import { useSimulationStore } from '../../lib/simulationStore'

export function PhoneSim() {
  const { notificationVisible, notificationText } = useSimulationStore()

  return (
    <div className="flex flex-col gap-3">
      {/* Panel label */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-muted tracking-widest uppercase">Phone</span>
        <span className="text-[10px] text-muted">notification</span>
      </div>

      {/* Phone frame */}
      <div className="relative mx-auto">
        {/* Phone body */}
        <div className="w-[160px] h-[280px] rounded-[28px] bg-card border border-border shadow-2xl overflow-hidden relative flex flex-col">
          {/* Status bar */}
          <div className="flex items-center justify-between px-5 pt-3 pb-1 bg-card">
            <span className="text-[9px] text-muted font-medium">9:41</span>
            <div className="flex items-center gap-0.5">
              {/* Signal bars */}
              {[1,2,3,4].map(i => (
                <div key={i} className={`w-0.5 rounded-full bg-text ${i <= 4 ? 'opacity-100' : 'opacity-30'}`} style={{ height: `${3 + i * 2}px` }} />
              ))}
              <svg width="12" height="9" viewBox="0 0 12 9" fill="none" className="ml-0.5">
                <path d="M6 9L0 3H4.5C4.5 3 5.5 5 6 5.5C6.5 5 7.5 3 7.5 3H12L6 9Z" fill="currentColor" className="text-text" opacity="0.7"/>
              </svg>
            </div>
          </div>

          {/* Notch */}
          <div className="w-14 h-4 bg-card rounded-b-2xl mx-auto mb-1 shrink-0" />

          {/* Screen content */}
          <div className="flex-1 bg-bg/50 flex flex-col items-center justify-center relative overflow-hidden">
            {/* Idle state */}
            {!notificationVisible && (
              <div className="text-center px-3">
                <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center mx-auto mb-2">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                  </svg>
                </div>
                <p className="text-[10px] text-muted leading-relaxed">Waiting for notifications</p>
              </div>
            )}

            {/* Notification */}
            {notificationVisible && (
              <div className="absolute inset-x-2 top-2 animate-slide-down">
                <div className="bg-card/95 border border-primary/30 rounded-xl p-3 shadow-xl shadow-primary/10">
                  {/* App icon + name */}
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-5 h-5 rounded-md bg-primary/20 flex items-center justify-center shrink-0">
                      <span className="text-[8px] font-bold text-primary">V</span>
                    </div>
                    <span className="text-[10px] font-semibold text-text">VyaparFlow</span>
                    <span className="text-[9px] text-muted ml-auto">now</span>
                  </div>
                  {/* Message */}
                  <p className="text-[10px] text-text leading-relaxed">{notificationText}</p>
                  {/* Action */}
                  <div className="flex gap-2 mt-2">
                    <button className="flex-1 py-1 rounded-md bg-primary text-white text-[9px] font-semibold">
                      View
                    </button>
                    <button className="flex-1 py-1 rounded-md border border-border text-muted text-[9px]">
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Home indicator */}
          <div className="w-24 h-1 bg-border rounded-full mx-auto mb-2 mt-auto" />
        </div>

        {/* Phone glow */}
        <div className="absolute inset-0 rounded-[28px] bg-primary/5 blur-xl -z-10" />
      </div>
    </div>
  )
}
