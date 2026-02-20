import { useState } from 'react'
import { getImageUrl } from '../api/client'
import { ImageOff } from 'lucide-react'

interface CardImageProps {
  productId: number
  alt: string
  size?: 'image_128' | 'image_256' | 'image_512' | 'image_1920'
  className?: string
}

export default function CardImage({ productId, alt, size = 'image_256', className = '' }: CardImageProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  return (
    <div className={`relative overflow-hidden bg-surface-100 dark:bg-surface-800 ${className}`}>
      {loading && !error && (
        <div className="absolute inset-0 card-image-placeholder" />
      )}

      {error ? (
        <div className="absolute inset-0 flex items-center justify-center text-surface-400">
          <ImageOff size={32} />
        </div>
      ) : (
        <img
          src={getImageUrl(productId, size)}
          alt={alt}
          className={`w-full h-full object-contain transition-opacity duration-200 ${loading ? 'opacity-0' : 'opacity-100'} ${size === 'image_1920' ? 'modal-card-image' : ''}`}
          onLoad={() => setLoading(false)}
          onError={() => {
            setLoading(false)
            setError(true)
          }}
          loading={size === 'image_1920' ? 'eager' : 'lazy'}
          decoding="async"
          fetchPriority={size === 'image_1920' ? 'high' : 'auto'}
        />
      )}
    </div>
  )
}
