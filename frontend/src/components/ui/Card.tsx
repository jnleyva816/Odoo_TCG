import { motion, HTMLMotionProps } from 'framer-motion'
import { cn } from '../../lib/utils'

interface CardProps extends HTMLMotionProps<'div'> {
    variant?: 'default' | 'glass' | 'elevated' | 'bordered'
    noPadding?: boolean
}

export const Card = ({ className, variant = 'default', noPadding = false, children, ...props }: CardProps) => {
    const baseStyles = 'rounded-xl overflow-hidden transition-all duration-300'

    const variants = {
        default: 'bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800/60 shadow-sm',
        glass: 'glass-card border-surface-200/40 dark:border-surface-700/40',
        elevated: 'bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 shadow-soft-lg hover:shadow-xl dark:shadow-glow/5',
        bordered: 'bg-transparent border border-surface-200 dark:border-surface-800',
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            whileHover={variant === 'elevated' || variant === 'glass' ? { y: -4 } : undefined}
            className={cn(
                baseStyles,
                variants[variant],
                noPadding ? 'p-0' : 'p-6',
                className
            )}
            {...props}
        >
            {children}
        </motion.div>
    )
}
