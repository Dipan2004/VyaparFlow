import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'destructive' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
}

const base = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/40'

const variants = {
  primary:    'bg-primary text-white hover:bg-primary/90 active:scale-[0.97]',
  ghost:      'bg-transparent text-muted hover:bg-card hover:text-text',
  destructive:'bg-destructive/10 text-destructive hover:bg-destructive/20 border border-destructive/20',
  outline:    'bg-transparent border border-border text-text hover:bg-card',
}

const sizes = {
  sm: 'h-7 px-3 text-[11px]',
  md: 'h-9 px-4 text-xs',
  lg: 'h-11 px-6 text-sm',
}

export function Button({ variant = 'primary', size = 'md', children, className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
