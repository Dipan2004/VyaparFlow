import type { ReactNode as _ReactNode } from 'react'

interface ToggleOption {
  value: string
  label: string
}

interface ToggleProps {
  options: [ToggleOption, ToggleOption]
  value: string
  onChange: (value: string) => void
}

export function Toggle({ options, value, onChange }: ToggleProps) {
  const activeIndex = options.findIndex(o => o.value === value)

  return (
    <div className="relative flex items-center bg-card border border-border rounded-lg p-0.5 gap-0.5">
      {/* Sliding indicator */}
      <div
        className="absolute top-0.5 bottom-0.5 bg-primary rounded-md transition-all duration-200"
        style={{
          left: activeIndex === 0 ? '3px' : 'calc(50% + 2px)',
          width: 'calc(50% - 5px)',
        }}
      />
      {options.map(option => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`relative z-10 flex-1 text-center py-1 px-3 rounded-md text-[11px] font-medium transition-colors duration-150 cursor-pointer ${
            option.value === value ? 'text-white' : 'text-muted hover:text-text'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
