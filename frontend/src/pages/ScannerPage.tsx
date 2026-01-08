import { useState, useCallback, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, X, Plus, Minus, Printer, Loader2, Package } from 'lucide-react'
import { searchCards, adjustStock, printLabel, Card } from '../api/client'
import CardImage from '../components/CardImage'

interface QueueItem {
  card: Card
  quantity: number
}

export default function ScannerPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Card[]>([])
  const [searching, setSearching] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Debounced search
  const performSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([])
      return
    }
    
    setSearching(true)
    try {
      const data = await searchCards(q, 20)
      setResults(data.cards)
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [])

  const handleInputChange = (value: string) => {
    setQuery(value)
    
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    
    debounceRef.current = setTimeout(() => {
      performSearch(value)
    }, 300)
  }

  // Add card to queue
  const addToQueue = (card: Card) => {
    setQueue(prev => {
      const existing = prev.find(item => item.card.id === card.id)
      if (existing) {
        return prev.map(item =>
          item.card.id === card.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        )
      }
      return [...prev, { card, quantity: 1 }]
    })
    
    // Clear search
    setQuery('')
    setResults([])
    inputRef.current?.focus()
  }

  // Remove from queue
  const removeFromQueue = (cardId: number) => {
    setQueue(prev => prev.filter(item => item.card.id !== cardId))
  }

  // Update queue quantity
  const updateQueueQuantity = (cardId: number, delta: number) => {
    setQueue(prev => prev.map(item => {
      if (item.card.id === cardId) {
        const newQty = Math.max(1, item.quantity + delta)
        return { ...item, quantity: newQty }
      }
      return item
    }))
  }

  // Process queue mutation (add to inventory)
  const processMutation = useMutation({
    mutationFn: async () => {
      for (const item of queue) {
        await adjustStock({
          product_id: item.card.id,
          quantity_change: item.quantity,
        })
      }
    },
    onSuccess: () => {
      setQueue([])
      inputRef.current?.focus()
    },
  })

  // Print labels mutation - prints one label per quantity
  const printMutation = useMutation({
    mutationFn: async () => {
      for (const item of queue) {
        // Print label once for each quantity
        for (let i = 0; i < item.quantity; i++) {
          await printLabel(item.card.id)
          // Small delay between prints to not overwhelm the printer
          if (i < item.quantity - 1) {
            await new Promise(resolve => setTimeout(resolve, 500))
          }
        }
      }
    },
    onSuccess: () => {
      // Don't clear queue after printing - user might want to add to inventory too
      inputRef.current?.focus()
    },
  })

  const totalItems = queue.reduce((sum, item) => sum + item.quantity, 0)

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="grid lg:grid-cols-[1fr,400px] gap-8">
        {/* Search Section */}
        <div>
          <h1 className="font-display text-3xl font-bold text-surface-900 dark:text-white mb-6">
            Card Scanner
          </h1>

          {/* Search Input */}
          <div className="relative mb-6">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => handleInputChange(e.target.value)}
              placeholder="Search by SKU or card name..."
              className="input pl-12 pr-12 py-3 text-lg"
              autoComplete="off"
            />
            {query && (
              <button
                onClick={() => {
                  setQuery('')
                  setResults([])
                  inputRef.current?.focus()
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
              >
                <X size={20} />
              </button>
            )}
          </div>

          {/* Search Results */}
          {searching && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
            </div>
          )}

          {!searching && results.length > 0 && (
            <div className="space-y-3">
              {results.map((card, index) => (
                <div
                  key={card.id}
                  className="card p-4 flex items-center gap-4 cursor-pointer hover:border-primary-500 transition-colors animate-fade-in"
                  style={{ animationDelay: `${index * 30}ms` }}
                  onClick={() => addToQueue(card)}
                >
                  <CardImage
                    productId={card.id}
                    alt={card.name}
                    size="image_128"
                    className="w-16 h-20 rounded-lg flex-shrink-0"
                  />
                  
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-surface-900 dark:text-white truncate">
                      {card.name}
                    </div>
                    <div className="text-sm text-surface-500 font-mono">
                      {card.sku}
                    </div>
                    <div className="text-sm text-surface-500">
                      {card.set_name || 'Unknown Set'}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="font-display font-bold text-lg text-surface-900 dark:text-white">
                      ${parseFloat(card.price).toFixed(2)}
                    </div>
                    <div className="text-sm text-surface-500">
                      Stock: {card.quantity}
                    </div>
                  </div>

                  <button className="btn btn-primary p-2">
                    <Plus size={20} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {!searching && query.length >= 2 && results.length === 0 && (
            <div className="text-center py-12 text-surface-500">
              <Package size={48} className="mx-auto mb-4 opacity-50" />
              <p>No cards found for "{query}"</p>
            </div>
          )}
        </div>

        {/* Queue Section */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-xl font-bold text-surface-900 dark:text-white">
                Queue
              </h2>
              <span className="bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 px-3 py-1 rounded-full text-sm font-medium">
                {totalItems} items
              </span>
            </div>

            {queue.length === 0 ? (
              <div className="text-center py-12 text-surface-500">
                <Package size={40} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">Scan cards to add them to the queue</p>
              </div>
            ) : (
              <>
                <div className="space-y-3 max-h-[400px] overflow-y-auto mb-6">
                  {queue.map(({ card, quantity }) => (
                    <div
                      key={card.id}
                      className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg"
                    >
                      <CardImage
                        productId={card.id}
                        alt={card.name}
                        size="image_128"
                        className="w-10 h-14 rounded flex-shrink-0"
                      />
                      
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-surface-900 dark:text-white truncate">
                          {card.name}
                        </div>
                        <div className="text-xs text-surface-500 font-mono">
                          {card.sku}
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => updateQueueQuantity(card.id, -1)}
                          className="p-1 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                        >
                          <Minus size={16} />
                        </button>
                        <span className="w-8 text-center font-mono text-sm">
                          {quantity}
                        </span>
                        <button
                          onClick={() => updateQueueQuantity(card.id, 1)}
                          className="p-1 text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                        >
                          <Plus size={16} />
                        </button>
                      </div>

                      <button
                        onClick={() => removeFromQueue(card.id)}
                        className="p-1 text-surface-400 hover:text-red-500"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <button
                    onClick={() => processMutation.mutate()}
                    disabled={processMutation.isPending}
                    className="btn btn-primary w-full py-3"
                  >
                    {processMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <Plus size={20} />
                        Add {totalItems} to Inventory
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => printMutation.mutate()}
                    disabled={printMutation.isPending}
                    className="btn btn-secondary w-full"
                  >
                    {printMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <Printer size={18} />
                        Print {totalItems} Labels
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => setQueue([])}
                    className="btn btn-ghost w-full text-surface-500"
                  >
                    Clear Queue
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}



