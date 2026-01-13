import { useEffect, useState } from 'react'
import { X, Plus, Minus, Printer, Loader2, CheckCircle, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCard, adjustStock, getPrinterStatus, printLabel, getPrinterPreviewUrl, getCardVariants } from '../api/client'
import CardImage from './CardImage'

interface CardModalProps {
  cardId: number
  onClose: () => void
}

// Helper to extract variant name from full card name
function getVariantLabel(name: string): string {
  const patterns = [
    /\((Reverse Holo(?:foil)?)\)\s*$/i,
    /\((Holo(?:foil)?)\)\s*$/i,
    /\((Cosmos Holo)\)\s*$/i,
    /-\s*(Reverse Holo(?:foil)?)\s*$/i,
    /-\s*(Holo(?:foil)?)\s*$/i,
  ]
  
  for (const pattern of patterns) {
    const match = name.match(pattern)
    if (match) return match[1]
  }
  return 'Normal'
}

export default function CardModal({ cardId, onClose }: CardModalProps) {
  const queryClient = useQueryClient()
  const [adjustAmount, setAdjustAmount] = useState(1)
  const [printStatus, setPrintStatus] = useState<'idle' | 'printing' | 'success' | 'error'>('idle')
  const [printMessage, setPrintMessage] = useState('')
  const [selectedVariantId, setSelectedVariantId] = useState<number>(cardId)

  // Fetch card variants
  const { data: variants = [], isLoading: variantsLoading } = useQuery({
    queryKey: ['card-variants', cardId],
    queryFn: () => getCardVariants(cardId),
  })

  // Fetch selected card details
  const { data: card, isLoading: cardLoading } = useQuery({
    queryKey: ['card', selectedVariantId],
    queryFn: () => getCard(selectedVariantId),
    enabled: selectedVariantId > 0,
  })

  // Fetch printer status
  const { data: printerStatus } = useQuery({
    queryKey: ['printer-status'],
    queryFn: getPrinterStatus,
    refetchInterval: 10000,
  })

  // Stock adjustment mutation
  const stockMutation = useMutation({
    mutationFn: adjustStock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['card', selectedVariantId] })
      queryClient.invalidateQueries({ queryKey: ['card-variants', cardId] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      queryClient.invalidateQueries({ queryKey: ['set-cards'] })
    },
  })

  // Print label mutation
  const printMutation = useMutation({
    mutationFn: () => printLabel(selectedVariantId),
    onMutate: () => {
      setPrintStatus('printing')
      setPrintMessage('')
    },
    onSuccess: (data) => {
      if (data.success) {
        setPrintStatus('success')
        setPrintMessage(data.message || 'Label printed!')
      } else {
        setPrintStatus('error')
        setPrintMessage(data.error || 'Print failed')
      }
      setTimeout(() => setPrintStatus('idle'), 3000)
    },
    onError: (error) => {
      setPrintStatus('error')
      setPrintMessage(error instanceof Error ? error.message : 'Print failed')
      setTimeout(() => setPrintStatus('idle'), 3000)
    },
  })

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Update selectedVariantId when cardId changes
  useEffect(() => {
    setSelectedVariantId(cardId)
  }, [cardId])

  const handleAdjust = (change: number) => {
    console.log('Stock adjustment:', { product_id: selectedVariantId, quantity_change: change, adjustAmount })
    stockMutation.mutate({
      product_id: selectedVariantId,
      quantity_change: change,
    })
  }

  const currentVariantIndex = variants.findIndex(v => v.id === selectedVariantId)
  const hasMultipleVariants = variants.length > 1

  const goToPrevVariant = () => {
    if (currentVariantIndex > 0) {
      setSelectedVariantId(variants[currentVariantIndex - 1].id)
    }
  }

  const goToNextVariant = () => {
    if (currentVariantIndex < variants.length - 1) {
      setSelectedVariantId(variants[currentVariantIndex + 1].id)
    }
  }

  const isLoading = variantsLoading || cardLoading

  if (isLoading) {
    return (
      <ModalWrapper onClose={onClose}>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
        </div>
      </ModalWrapper>
    )
  }

  if (!card) {
    return (
      <ModalWrapper onClose={onClose}>
        <div className="text-center py-12 text-surface-500">
          Card not found
        </div>
      </ModalWrapper>
    )
  }

  return (
    <ModalWrapper onClose={onClose}>
      {/* Variant Toggle - At the top if multiple variants exist */}
      {hasMultipleVariants && (
        <div className="mb-2 md:mb-6">
          <div className="flex items-center justify-center gap-1 md:gap-2">
            <button
              onClick={goToPrevVariant}
              disabled={currentVariantIndex === 0}
              className="p-2 rounded-lg text-surface-500 hover:text-surface-900 dark:hover:text-white hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={20} />
            </button>
            
            <div className="flex gap-1 md:gap-1.5 overflow-x-auto py-1 px-1 md:px-2">
              {variants.map((variant) => {
                const label = getVariantLabel(variant.name)
                const isSelected = variant.id === selectedVariantId
                return (
                  <button
                    key={variant.id}
                    onClick={() => setSelectedVariantId(variant.id)}
                    className={`px-2 md:px-3 py-1 md:py-1.5 rounded-full text-xs md:text-sm font-medium whitespace-nowrap transition-all ${
                      isSelected
                        ? 'bg-primary-500 text-white shadow-sm'
                        : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
                    }`}
                  >
                    {label}
                    <span className={`ml-1 md:ml-1.5 text-xs ${isSelected ? 'text-primary-100' : 'text-surface-400'}`}>
                      ({variant.quantity})
                    </span>
                  </button>
                )
              })}
            </div>
            
            <button
              onClick={goToNextVariant}
              disabled={currentVariantIndex === variants.length - 1}
              className="p-2 rounded-lg text-surface-500 hover:text-surface-900 dark:hover:text-white hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-col md:grid md:grid-cols-2 gap-3 md:gap-6">
        {/* Card Image - native resolution, centered with contrasting background */}
        <div className="flex justify-center items-center">
          <div className="bg-black dark:bg-white rounded-lg md:rounded-xl p-2 md:p-4 shadow-lg">
            <div className="w-[120px] h-[167px] md:w-[200px] md:h-[279px] overflow-hidden rounded-md md:rounded-lg">
              <CardImage productId={selectedVariantId} alt={card.name} size="image_256" className="w-full h-full" />
            </div>
          </div>
        </div>

        {/* Card Info */}
        <div className="flex flex-col">
          <h2 className="font-display font-bold text-base md:text-2xl text-surface-900 dark:text-white mb-1 md:mb-2 text-center md:text-left">
            {card.name}
          </h2>
          
          <div className="space-y-1 md:space-y-3 text-xs md:text-sm mb-2 md:mb-6">
            <InfoRow label="SKU" value={card.sku} mono />
            <InfoRow label="Set" value={card.set_name || 'N/A'} />
            <InfoRow label="Price" value={`$${parseFloat(card.price).toFixed(2)}`} />
            {card.barcode && <InfoRow label="Barcode" value={card.barcode} mono />}
          </div>

          {/* Stock Management */}
          <div className="bg-surface-100 dark:bg-surface-800 rounded-lg md:rounded-xl p-2 md:p-4 mb-2 md:mb-6">
            <div className="text-xs md:text-sm font-medium text-surface-500 dark:text-surface-400 mb-1 md:mb-2">
              Current Stock
            </div>
            <div className="flex items-center justify-between">
              <span className="font-display text-2xl md:text-4xl font-bold text-surface-900 dark:text-white">
                {stockMutation.isPending ? '...' : card.quantity}
              </span>
              
              <div className="flex items-center gap-1 md:gap-2">
                <button
                  onClick={() => handleAdjust(-adjustAmount)}
                  disabled={stockMutation.isPending || card.quantity < adjustAmount}
                  className="btn btn-secondary p-1.5 md:p-3"
                >
                  <Minus size={16} className="md:w-[18px] md:h-[18px]" />
                </button>
                
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-10 md:w-16 text-center input text-xs md:text-sm py-1 md:py-2"
                />
                
                <button
                  onClick={() => handleAdjust(adjustAmount)}
                  disabled={stockMutation.isPending}
                  className="btn btn-primary p-1.5 md:p-3"
                >
                  <Plus size={16} className="md:w-[18px] md:h-[18px]" />
                </button>
              </div>
            </div>
          </div>

          {/* Label Preview - hidden on mobile */}
          <div className="hidden md:block mb-4 md:mb-6">
            <div className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-2">
              Label Preview
            </div>
            <div className="flex justify-center">
              <div className="bg-surface-100 dark:bg-surface-800 p-2 rounded-lg overflow-hidden rotate-90">
                <img
                  src={getPrinterPreviewUrl(selectedVariantId)}
                  alt="Label preview"
                  className="max-h-[200px] w-auto"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="mt-auto flex flex-col gap-1.5 md:gap-3">
            <button
              onClick={() => printMutation.mutate()}
              disabled={!printerStatus?.connected || printStatus === 'printing'}
              className={`btn flex-1 text-xs md:text-base py-1.5 md:py-2.5 ${
                printStatus === 'success' 
                  ? 'btn-success bg-green-600 hover:bg-green-700' 
                  : printStatus === 'error'
                  ? 'btn-error bg-red-600 hover:bg-red-700'
                  : 'btn-primary'
              }`}
            >
              {printStatus === 'printing' ? (
                <>
                  <Loader2 size={16} className="animate-spin md:w-[18px] md:h-[18px]" />
                  Printing...
                </>
              ) : printStatus === 'success' ? (
                <>
                  <CheckCircle size={16} className="md:w-[18px] md:h-[18px]" />
                  Printed!
                </>
              ) : printStatus === 'error' ? (
                <>
                  <AlertCircle size={16} className="md:w-[18px] md:h-[18px]" />
                  Failed
                </>
              ) : (
                <>
                  <Printer size={16} className="md:w-[18px] md:h-[18px]" />
                  Print Label
                </>
              )}
            </button>
            {printerStatus && !printerStatus.connected && (
              <p className="text-xs text-center text-surface-500">
                {printerStatus.enabled ? `Printer offline (${printerStatus.ip})` : 'Printer not configured'}
              </p>
            )}
            {!printerStatus && (
              <p className="text-xs text-center text-surface-500">
                Checking printer status...
              </p>
            )}
            {printMessage && printStatus !== 'idle' && (
              <p className={`text-xs text-center ${printStatus === 'error' ? 'text-red-500' : 'text-green-500'}`}>
                {printMessage}
              </p>
            )}
          </div>
        </div>
      </div>
    </ModalWrapper>
  )
}

function ModalWrapper({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 md:p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-surface-900 rounded-xl md:rounded-2xl shadow-2xl w-full max-w-3xl max-h-[95vh] md:max-h-[90vh] overflow-y-auto animate-slide-up">
        <button
          onClick={onClose}
          className="absolute top-2 right-2 md:top-4 md:right-4 p-2 rounded-lg text-surface-500 hover:text-surface-900 dark:hover:text-white hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors z-10"
        >
          <X size={20} />
        </button>
        
        <div className="p-3 md:p-6">
          {children}
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-surface-500 dark:text-surface-400">{label}</span>
      <span className={`text-surface-900 dark:text-white ${mono ? 'font-mono text-xs md:text-sm' : ''}`}>
        {value}
      </span>
    </div>
  )
}
