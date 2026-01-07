import { useEffect, useState } from 'react'
import { X, Plus, Minus, Printer, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCard, adjustStock, getPrinterStatus, printLabel, getPrinterPreviewUrl } from '../api/client'
import CardImage from './CardImage'

interface CardModalProps {
  cardId: number
  onClose: () => void
}

export default function CardModal({ cardId, onClose }: CardModalProps) {
  const queryClient = useQueryClient()
  const [adjustAmount, setAdjustAmount] = useState(1)
  const [printStatus, setPrintStatus] = useState<'idle' | 'printing' | 'success' | 'error'>('idle')
  const [printMessage, setPrintMessage] = useState('')

  // Fetch card details
  const { data: card, isLoading } = useQuery({
    queryKey: ['card', cardId],
    queryFn: () => getCard(cardId),
  })

  // Fetch printer status
  const { data: printerStatus } = useQuery({
    queryKey: ['printer-status'],
    queryFn: getPrinterStatus,
    refetchInterval: 10000, // Check every 10s
  })

  // Stock adjustment mutation
  const stockMutation = useMutation({
    mutationFn: adjustStock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['card', cardId] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
    },
  })

  // Print label mutation
  const printMutation = useMutation({
    mutationFn: () => printLabel(cardId),
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
      // Reset status after 3 seconds
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

  const handleAdjust = (change: number) => {
    stockMutation.mutate({
      product_id: cardId,
      quantity_change: change,
    })
  }

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
      <div className="flex flex-col md:grid md:grid-cols-2 gap-4 md:gap-6">
        {/* Card Image - native resolution, centered with contrasting background */}
        <div className="flex justify-center items-center">
          <div className="bg-black dark:bg-white rounded-xl p-4 shadow-lg">
            <div className="w-[200px] h-[279px] overflow-hidden rounded-lg">
              <CardImage productId={card.id} alt={card.name} size="image_256" className="w-full h-full" />
            </div>
          </div>
        </div>

        {/* Card Info */}
        <div className="flex flex-col">
          <h2 className="font-display font-bold text-lg md:text-2xl text-surface-900 dark:text-white mb-2 text-center md:text-left">
            {card.name}
          </h2>
          
          <div className="space-y-2 md:space-y-3 text-sm mb-4 md:mb-6">
            <InfoRow label="SKU" value={card.sku} mono />
            <InfoRow label="Set" value={card.set_name || 'N/A'} />
            <InfoRow label="Price" value={`$${parseFloat(card.price).toFixed(2)}`} />
            {card.barcode && <InfoRow label="Barcode" value={card.barcode} mono />}
          </div>

          {/* Stock Management */}
          <div className="bg-surface-100 dark:bg-surface-800 rounded-xl p-3 md:p-4 mb-4 md:mb-6">
            <div className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-2">
              Current Stock
            </div>
            <div className="flex items-center justify-between">
              <span className="font-display text-3xl md:text-4xl font-bold text-surface-900 dark:text-white">
                {stockMutation.isPending ? '...' : card.quantity}
              </span>
              
              <div className="flex items-center gap-1 md:gap-2">
                <button
                  onClick={() => handleAdjust(-adjustAmount)}
                  disabled={stockMutation.isPending || card.quantity < adjustAmount}
                  className="btn btn-secondary p-2 md:p-3"
                >
                  <Minus size={18} />
                </button>
                
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-12 md:w-16 text-center input text-sm"
                />
                
                <button
                  onClick={() => handleAdjust(adjustAmount)}
                  disabled={stockMutation.isPending}
                  className="btn btn-primary p-2 md:p-3"
                >
                  <Plus size={18} />
                </button>
              </div>
            </div>
          </div>

          {/* Label Preview */}
          <div className="mb-4 md:mb-6">
            <div className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-2">
              Label Preview
            </div>
            <div className="bg-white border border-surface-200 dark:border-surface-700 rounded-lg p-2 md:p-3 flex justify-center">
              <img
                src={getPrinterPreviewUrl(cardId)}
                alt="Label preview"
                className="max-w-full h-auto"
                style={{ maxHeight: '120px' }}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="mt-auto flex flex-col gap-2 md:gap-3">
            <button
              onClick={() => printMutation.mutate()}
              disabled={!printerStatus?.connected || printStatus === 'printing'}
              className={`btn flex-1 text-sm md:text-base py-2 md:py-2.5 ${
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
        
        <div className="p-4 md:p-6">
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
