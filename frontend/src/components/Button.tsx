import type { ComponentProps, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { cx } from '@/lib/cx'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2 font-medium whitespace-nowrap select-none rounded-md ' +
  'transition-[background-color,border-color,color,transform,box-shadow] duration-[var(--dur)] ease-out ' +
  'active:scale-[.97] disabled:opacity-45 disabled:active:scale-100'

const variants: Record<Variant, string> = {
  // 主要按鈕：石墨色，像 2B 鉛筆塗滿
  primary: 'bg-ink text-paper hover:bg-ink-soft shadow-[0_1px_0_rgb(0_0_0/.15)]',
  // 次要按鈕：原子筆藍的框
  secondary: 'border border-rule text-accent-strong bg-sheet hover:border-accent hover:bg-accent-faint',
  ghost: 'text-ink-soft hover:bg-accent-faint hover:text-ink',
  danger: 'border border-bad/40 text-bad bg-sheet hover:bg-bad-soft',
}

const sizes: Record<Size, string> = {
  sm: 'hit h-9 px-3 text-sm',
  md: 'h-11 px-4 text-base',
  lg: 'h-13 px-6 text-base',
}

interface CommonProps {
  variant?: Variant
  size?: Size
  children: ReactNode
  className?: string
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: CommonProps & ComponentProps<'button'>) {
  return <button type={type} className={cx(base, variants[variant], sizes[size], className)} {...props} />
}

export function ButtonLink({ variant = 'primary', size = 'md', className, ...props }: CommonProps & LinkProps) {
  return <Link className={cx(base, variants[variant], sizes[size], className)} {...props} />
}
