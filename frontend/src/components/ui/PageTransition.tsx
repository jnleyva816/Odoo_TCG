import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface PageTransitionProps {
    children: ReactNode
    className?: string
}

export const PageTransition = ({ children, className }: PageTransitionProps) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
            transition={{
                duration: 0.4,
                ease: [0.16, 1, 0.3, 1] // Apple's sweet spot ease
            }}
            className={className}
        >
            {children}
        </motion.div>
    )
}
