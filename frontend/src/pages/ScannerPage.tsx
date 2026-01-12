import { useState, useCallback, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, X, Plus, Minus, Printer, Loader2, Package, Check } from 'lucide-react'
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

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

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
    
    setQuery('')
    setResults([])
    inputRef.current?.focus()
  }

  const removeFromQueue = (cardId: number) => {
    setQueue(prev => prev.filter(item => item.card.id !== cardId))
  }

  const updateQueueQuantity = (cardId: number, delta: number) => {
    setQueue(prev => prev.map(item => {
      if (item.card.id === cardId) {
        const newQty = Math.max(1, item.quantity + delta)
        return { ...item, quantity: newQty }
      }
      return item
    }))
  }

  const [processedItems, setProcessedItems] = useState<Set<number>>(new Set())

  const processMutation = useMutation({
    mutationFn: async () => {
      const processed = new Set<number>()
      for (const item of queue) {
        await adjustStock({
          product_id: item.card.id,
          quantity_change: item.quantity,
        })
        processed.add(item.card.id)
      }
      return processed
    },
    onSuccess: (processed) => {
      // Mark items as processed but don't clear queue
      setProcessedItems(prev => new Set([...prev, ...processed]))
      inputRef.current?.focus()
    },
  })

  const printMutation = useMutation({
    mutationFn: async () => {
      for (const item of queue) {
        for (let i = 0; i < item.quantity; i++) {
          await printLabel(item.card.id)
          if (i < item.quantity - 1) {
            await new Promise(resolve => setTimeout(resolve, 500))
          }
        }
      }
    },
    onSuccess: () => {
      inputRef.current?.focus()
    },
  })

  const totalItems = queue.reduce((sum, item) => sum + item.quantity, 0)

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 lg:py-8">
      <div className="grid lg:grid-cols-[1fr,360px] gap-6 lg:gap-8">
        {/* Search Section */}
        <div className="animate-slide-in-up">
          <h1 className="text-2xl font-semibold text-surface-900 dark:text-white mb-6">
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
              className="input-lg pl-12 pr-12"
              autoComplete="off"
            />
            {query && (
              <button
                onClick={() => {
                  setQuery('')
                  setResults([])
                  inputRef.current?.focus()
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-400 hover:text-primary-500 transition-colors"
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
            <div className="space-y-2">
              {results.map((card, index) => (
                <div
                  key={card.id}
                  className="card p-4 flex items-center gap-4 cursor-pointer hover:border-primary-500 hover:shadow-soft transition-all animate-fade-in"
                  style={{ animationDelay: `${index * 30}ms` }}
                  onClick={() => addToQueue(card)}
                >
                  <CardImage
                    productId={card.id}
                    alt={card.name}
                    size="image_128"
                    className="w-12 h-16 rounded-lg flex-shrink-0"
                  />
                  
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-surface-900 dark:text-white truncate">
                      {card.name}
                    </div>
                    <div className="text-sm text-surface-500 font-mono">
                      {card.sku}
                    </div>
                    <div className="text-sm text-surface-400">
                      {card.set_name || 'Unknown Set'}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="font-semibold text-lg text-surface-900 dark:text-white">
                      ${parseFloat(card.price).toFixed(2)}
                    </div>
                    <div className="text-sm text-surface-500">
                      Stock: {card.quantity}
                    </div>
                  </div>

                  <button className="btn btn-primary p-2.5 rounded-xl">
                    <Plus size={18} />
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
        <div className="lg:sticky lg:top-4 lg:self-start animate-slide-in-right">
          <div className="card">
            <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center justify-between">
              <h2 className="font-semibold text-surface-900 dark:text-white">
                Queue
              </h2>
              <span className="badge badge-primary">
                {totalItems}
              </span>
            </div>

            {queue.length === 0 ? (
              <div className="p-8 text-center text-surface-500">
                <Package size={40} className="mx-auto mb-3 opacity-50" />
                <p className="text-sm">Scan cards to add them to the queue</p>
              </div>
            ) : (
              <>
                <div className="max-h-[360px] overflow-y-auto">
                  {queue.map(({ card, quantity }, index) => {
                    const isProcessed = processedItems.has(card.id)
                    return (
                    <div
                      key={card.id}
                      className={`flex items-center gap-3 p-3 border-b border-surface-100 dark:border-surface-800 animate-fade-in ${
                        isProcessed ? 'bg-green-50 dark:bg-green-900/20' : ''
                      }`}
                      style={{ animationDelay: `${index * 30}ms` }}
                    >
                      <div className="relative">
                        <CardImage
                          productId={card.id}
                          alt={card.name}
                          size="image_128"
                          className="w-10 h-14 rounded flex-shrink-0"
                        />
                        {isProcessed && (
                          <div className="absolute -top-1 -right-1 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                            <Check size={12} className="text-white" />
                          </div>
                        )}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-surface-900 dark:text-white truncate">
                          {card.name}
                        </div>
                        <div className="text-xs text-surface-500 font-mono">
                          {card.sku}
                        </div>
                        {isProcessed && (
                          <div className="text-xs text-green-600 dark:text-green-400">
                            Added to inventory
                          </div>
                        )}
                      </div>

                      <div className="flex items-center bg-surface-100 dark:bg-surface-800 rounded-lg">
                        <button
                          onClick={() => updateQueueQuantity(card.id, -1)}
                          className="p-2 text-surface-500 hover:text-primary-500 transition-colors"
                        >
                          <Minus size={14} />
                        </button>
                        <span className="w-8 text-center font-mono text-sm font-medium text-surface-900 dark:text-white">
                          {quantity}
                        </span>
                        <button
                          onClick={() => updateQueueQuantity(card.id, 1)}
                          className="p-2 text-surface-500 hover:text-primary-500 transition-colors"
                        >
                          <Plus size={14} />
                        </button>
                      </div>

                      <button
                        onClick={() => removeFromQueue(card.id)}
                        className="p-1.5 text-surface-400 hover:text-red-500 transition-colors"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  )})}
                </div>

                <div className="p-4 space-y-2 border-t border-surface-200 dark:border-surface-800">
                  <button
                    onClick={() => processMutation.mutate()}
                    disabled={processMutation.isPending || queue.every(item => processedItems.has(item.card.id))}
                    className={`btn w-full py-3 ${
                      queue.every(item => processedItems.has(item.card.id))
                        ? 'btn-success bg-green-600 hover:bg-green-700'
                        : 'btn-primary'
                    }`}
                  >
                    {processMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : queue.every(item => processedItems.has(item.card.id)) ? (
                      <>
                        <Check size={18} />
                        All Added to Inventory
                      </>
                    ) : (
                      <>
                        <Plus size={18} />
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
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to clear ${queue.length} items from the queue?`)) {
                        setQueue([])
                        setProcessedItems(new Set())
                      }
                    }}
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
