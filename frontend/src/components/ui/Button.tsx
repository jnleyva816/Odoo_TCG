import React from 'react'
import { motion, HTMLMotionProps } from 'framer-motion'
import { cn } from '../../lib/utils'
import { Loader2 } from 'lucide-react'

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
    size?: 'sm' | 'md' | 'lg' | 'icon'
    isLoading?: boolean
    leftIcon?: React.ReactNode
    rightIcon?: React.ReactNode
    children?: React.ReactNode
}

const variants = {
    primary: 'bg-primary-600 text-white hover:bg-primary-500 shadow-lg shadow-primary-500/25 border border-primary-500/50',
    secondary: 'bg-surface-100 text-surface-900 hover:bg-surface-200 dark:bg-surface-800 dark:text-surface-50 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-700',
    outline: 'bg-transparent border border-surface-300 dark:border-surface-700 text-surface-700 dark:text-surface-300 hover:bg-surface-50 dark:hover:bg-surface-800',
    ghost: 'bg-transparent text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800',
    danger: 'bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-500/25',
}

const sizes = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
    icon: 'h-10 w-10 p-2',
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = 'primary', size = 'md', isLoading, leftIcon, rightIcon, children, disabled, ...props }, ref) => {
        return (
            <motion.button
                ref={ref}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={cn(
                    'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:pointer-events-none disabled:opacity-50 select-none',
                    variants[variant],
                    sizes[size],
                    className
                )}
                disabled={disabled || isLoading}
                {...props}
            >
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {!isLoading && leftIcon && <div className="text-current opacity-80">{leftIcon}</div>}
                {children}
                {!isLoading && rightIcon && <div className="text-current opacity-80">{rightIcon}</div>}
            </motion.button>
        )
    }
)

Button.displayName = 'Button'
