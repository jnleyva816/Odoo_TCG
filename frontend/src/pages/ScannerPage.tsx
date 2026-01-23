import { useState, useCallback, useRef, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Search, X, Plus, Minus, Printer, Loader2, Package, Check,
  Camera, Upload, Zap, AlertCircle, RefreshCw
} from 'lucide-react'
import {
  searchCards, adjustStock, printLabel, Card,
  getScannerStatus, scanImage, scanBase64Image, CardMatch, ScanResult
} from '../api/client'
import CardImage from '../components/CardImage'

interface QueueItem {
  card: Card
  quantity: number
}

type ScanMode = 'search' | 'camera'

export default function ScannerPage() {
  const [mode, setMode] = useState<ScanMode>('search')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Card[]>([])
  const [searching, setSearching] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [processedItems, setProcessedItems] = useState<Set<number>>(new Set())
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Camera state
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [lastMatches, setLastMatches] = useState<CardMatch[]>([])
  const [scanning, setScanning] = useState(false)
  const [autoScan, setAutoScan] = useState(false)
  const autoScanRef = useRef<ReturnType<typeof setInterval>>()

  // Modal state for scan results
  const [showScanModal, setShowScanModal] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  // Scanner status
  const { data: scannerStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['scanner-status'],
    queryFn: getScannerStatus,
    refetchInterval: 30000, // Refresh every 30s
  })

  useEffect(() => {
    if (mode === 'search') {
      inputRef.current?.focus()
    }
  }, [mode])

  // Cleanup camera on unmount
  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
      }
      if (autoScanRef.current) {
        clearInterval(autoScanRef.current)
      }
    }
  }, [stream])

  // ==========================================================================
  // Search Mode Functions
  // ==========================================================================

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

  // ==========================================================================
  // Camera Mode Functions
  // ==========================================================================

  const startCamera = async () => {
    try {
      // Stop any existing stream
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
        setStream(null)
      }

      const attachStream = async (mediaStream: MediaStream): Promise<boolean> => {
        const video = videoRef.current
        if (!video) {
          console.error('Video element not found')
          return false
        }

        setStream(mediaStream)
        video.srcObject = mediaStream

        // Wait for video to be ready with proper event handling
        return new Promise((resolve) => {
          const handleLoadedMetadata = () => {
            video.removeEventListener('loadedmetadata', handleLoadedMetadata)
            video.removeEventListener('error', handleError)
            
            video.play()
              .then(() => {
                // Give a brief moment for dimensions to be available
                setTimeout(() => {
                  const hasFrames = (video.videoWidth ?? 0) > 0 && (video.videoHeight ?? 0) > 0
                  resolve(hasFrames)
                }, 100)
              })
              .catch(() => {
                // Autoplay might be blocked, but stream may still work
                setTimeout(() => {
                  const hasFrames = (video.videoWidth ?? 0) > 0 && (video.videoHeight ?? 0) > 0
                  resolve(hasFrames)
                }, 100)
              })
          }

          const handleError = () => {
            video.removeEventListener('loadedmetadata', handleLoadedMetadata)
            video.removeEventListener('error', handleError)
            resolve(false)
          }

          video.addEventListener('loadedmetadata', handleLoadedMetadata)
          video.addEventListener('error', handleError)

          // Fallback timeout in case events don't fire
          setTimeout(() => {
            video.removeEventListener('loadedmetadata', handleLoadedMetadata)
            video.removeEventListener('error', handleError)
            const hasFrames = (video.videoWidth ?? 0) > 0 && (video.videoHeight ?? 0) > 0
            resolve(hasFrames)
          }, 3000)
        })
      }

      const preferredConstraints = {
        video: {
          facingMode: 'environment', // Prefer back camera on mobile
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      }

      const fallbackConstraints = { video: true }

      let mediaStream = await navigator.mediaDevices.getUserMedia(preferredConstraints)
      let attached = await attachStream(mediaStream)

      if (!attached) {
        console.log('Preferred camera constraints failed, trying fallback...')
        mediaStream.getTracks().forEach(track => track.stop())
        mediaStream = await navigator.mediaDevices.getUserMedia(fallbackConstraints)
        attached = await attachStream(mediaStream)
      }

      if (!attached) {
        throw new Error('Camera stream started but no frames were received.')
      }

      setCameraActive(true)
    } catch (err) {
      console.error('Failed to access camera:', err)
      alert('Could not access camera. Please ensure camera permissions are granted.')
    }
  }

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }
    setCameraActive(false)
    setAutoScan(false)
    if (autoScanRef.current) {
      clearInterval(autoScanRef.current)
    }
  }

  const captureFrame = (): string | null => {
    if (!videoRef.current || !canvasRef.current) return null

    const video = videoRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    ctx.drawImage(video, 0, 0)

    return canvas.toDataURL('image/jpeg', 0.8)
  }

  const scanCurrentFrame = async () => {
    if (scanning) return

    const imageData = captureFrame()
    if (!imageData) return

    setScanning(true)
    setScanError(null)
    try {
      const response = await scanBase64Image(imageData, false)
      if (response.success) {
        setScanResult(response.result)
        if (response.result.matches.length > 0) {
          setLastMatches(response.result.matches)
          setShowScanModal(true)
        } else {
          setScanError('No cards detected in this frame. Try adjusting the camera angle.')
          setShowScanModal(true)
        }
      }
    } catch (err) {
      console.error('Scan failed:', err)
      setScanError('Scan failed. Please try again.')
      setShowScanModal(true)
    } finally {
      setScanning(false)
    }
  }

  const toggleAutoScan = () => {
    if (autoScan) {
      setAutoScan(false)
      if (autoScanRef.current) {
        clearInterval(autoScanRef.current)
      }
    } else {
      setAutoScan(true)
      // Scan every 1.5 seconds
      autoScanRef.current = setInterval(() => {
        scanCurrentFrame()
      }, 1500)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setScanning(true)
    setScanError(null)
    try {
      const response = await scanImage(file, false)
      if (response.success) {
        setScanResult(response.result)
        if (response.result.matches.length > 0) {
          setLastMatches(response.result.matches)
          setShowScanModal(true)
        } else {
          setScanError('No cards detected in this image.')
          setShowScanModal(true)
        }
      }
    } catch (err) {
      console.error('Scan failed:', err)
      setScanError('Scan failed. Please try again.')
      setShowScanModal(true)
    } finally {
      setScanning(false)
      // Reset file input so the same file can be uploaded again
      e.target.value = ''
    }
  }

  const addMatchToQueue = (match: CardMatch, closeModal = false) => {
    // CardMatch now contains the Odoo product ID directly
    const card: Card = {
      id: match.card_id,
      sku: match.sku,
      name: match.name,
      set_name: match.set_name,
      quantity: match.quantity,
      price: String(match.price),
      has_image: true,
    }
    addToQueue(card)
    if (closeModal) {
      setShowScanModal(false)
      setScanError(null)
    }
  }

  const closeScanModal = () => {
    setShowScanModal(false)
    setScanError(null)
  }

  // ==========================================================================
  // Queue Processing
  // ==========================================================================

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

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 lg:py-8">
      <div className="grid lg:grid-cols-[1fr,360px] gap-6 lg:gap-8">
        {/* Main Section */}
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-semibold text-surface-900 dark:text-white">
              Card Scanner
            </h1>

            {/* Mode Toggle */}
            <div className="flex bg-surface-100 dark:bg-surface-800 rounded-lg p-1">
              <button
                onClick={() => { setMode('search'); stopCamera() }}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${mode === 'search'
                  ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
                  : 'text-surface-500 hover:text-surface-700'
                  }`}
              >
                <Search size={16} className="inline mr-2" />
                Search
              </button>
              <button
                onClick={() => setMode('camera')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${mode === 'camera'
                  ? 'bg-white dark:bg-surface-700 text-surface-900 dark:text-white shadow-sm'
                  : 'text-surface-500 hover:text-surface-700'
                  }`}
              >
                <Camera size={16} className="inline mr-2" />
                Camera
              </button>
            </div>
          </div>

          {/* Scanner Status */}
          {mode === 'camera' && (
            <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${scannerStatus?.ready
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
              : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'
              }`}>
              {statusLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : scannerStatus?.ready ? (
                <Check size={16} />
              ) : (
                <AlertCircle size={16} />
              )}
              <span className="text-sm">
                {statusLoading ? 'Checking scanner...' :
                  scannerStatus?.ready
                    ? `Scanner ready (${scannerStatus.hash_count.toLocaleString()} cards in database)`
                    : scannerStatus?.message || 'Scanner not fully initialized'}
              </span>
            </div>
          )}

          {/* Search Mode */}
          {mode === 'search' && (
            <>
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
            </>
          )}

          {/* Camera Mode */}
          {mode === 'camera' && (
            <div className="space-y-4">
              {/* Video / Upload Area */}
              <div className="relative aspect-video bg-surface-900 rounded-xl overflow-hidden">
                {/* Always render video element to ensure ref is available */}
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={`w-full h-full object-cover ${cameraActive ? '' : 'hidden'}`}
                />
                {/* Card positioning guide - shown when camera is active but no detections yet */}
                {cameraActive && !scanning && (!scanResult?.detections?.length) && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-2 border-dashed border-white/40 rounded-lg"
                      style={{ width: '40%', aspectRatio: '2.5/3.5' }}>
                      <div className="w-full h-full flex items-center justify-center text-white/60 text-sm text-center p-2">
                        Position card here
                      </div>
                    </div>
                  </div>
                )}
                {cameraActive && scanning && (
                  <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
                    <Loader2 className="w-12 h-12 animate-spin text-white" />
                  </div>
                )}
                {/* Detection overlay */}
                {cameraActive && scanResult?.detections?.map((det, i) => (
                  <div
                    key={i}
                    className="absolute border-2 border-green-500 bg-green-500/20 rounded"
                    style={{
                      left: `${(det.bbox[0] / (scanResult.image_size[0] || 1)) * 100}%`,
                      top: `${(det.bbox[1] / (scanResult.image_size[1] || 1)) * 100}%`,
                      width: `${(det.width / (scanResult.image_size[0] || 1)) * 100}%`,
                      height: `${(det.height / (scanResult.image_size[1] || 1)) * 100}%`,
                    }}
                  >
                    <span className="absolute -top-5 left-0 text-xs bg-green-500 text-white px-1 rounded">
                      {(det.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
                {!cameraActive && (
                  <div className="w-full h-full flex flex-col items-center justify-center text-surface-400">
                    <Camera size={64} className="mb-4" />
                    <p className="text-lg mb-4">Camera not active</p>
                    <div className="flex gap-3">
                      <button onClick={startCamera} className="btn btn-primary">
                        <Camera size={18} />
                        Start Camera
                      </button>
                      <label className="btn btn-secondary cursor-pointer">
                        <Upload size={18} />
                        Upload Image
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleFileUpload}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>
                )}
                <canvas ref={canvasRef} className="hidden" />
              </div>

              {/* Camera Controls */}
              {cameraActive && (
                <>
                  <div className="flex gap-3">
                    <button
                      onClick={scanCurrentFrame}
                      disabled={scanning}
                      className="btn btn-primary flex-1"
                    >
                      {scanning ? (
                        <Loader2 size={18} className="animate-spin" />
                      ) : (
                        <Zap size={18} />
                      )}
                      Scan Now
                    </button>
                    <button
                      onClick={toggleAutoScan}
                      className={`btn ${autoScan ? 'btn-success' : 'btn-secondary'}`}
                    >
                      <RefreshCw size={18} className={autoScan ? 'animate-spin' : ''} />
                      {autoScan ? 'Auto: ON' : 'Auto: OFF'}
                    </button>
                    <button onClick={stopCamera} className="btn btn-ghost">
                      <X size={18} />
                      Stop
                    </button>
                  </div>
                  <p className="text-xs text-surface-500 text-center">
                    Tip: Hold card flat, fill most of the frame, and avoid glare for best results
                  </p>
                </>
              )}

              {/* Scan Results */}
              {lastMatches.length > 0 && (
                <div className="card">
                  <div className="p-3 border-b border-surface-200 dark:border-surface-800">
                    <h3 className="font-semibold text-surface-900 dark:text-white">
                      Detected Cards
                    </h3>
                    {scanResult && (
                      <p className="text-xs text-surface-500">
                        Processed in {scanResult.processing_time_ms.toFixed(0)}ms
                      </p>
                    )}
                  </div>
                  <div className="divide-y divide-surface-100 dark:divide-surface-800">
                    {lastMatches.map((match, index) => (
                      <div
                        key={index}
                        className="p-3 flex items-center gap-3 hover:bg-surface-50 dark:hover:bg-surface-800/50"
                      >
                        <CardImage
                          productId={match.card_id}
                          alt={match.name}
                          size="image_128"
                          className="w-10 h-14 rounded flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-surface-900 dark:text-white truncate">
                            {match.name}
                          </div>
                          <div className="text-sm text-surface-500">
                            {match.set_name}
                          </div>
                          <div className="text-xs text-surface-400">
                            {match.sku} • Stock: {match.quantity} • ${match.price.toFixed(2)}
                          </div>
                          <div className="text-xs text-green-600 dark:text-green-400">
                            {(match.confidence * 100).toFixed(1)}% match
                          </div>
                        </div>
                        <button
                          onClick={() => addMatchToQueue(match)}
                          className="btn btn-primary p-2"
                        >
                          <Plus size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
                <p className="text-sm">
                  {mode === 'search'
                    ? 'Search cards to add them to the queue'
                    : 'Scan cards to add them to the queue'}
                </p>
              </div>
            ) : (
              <>
                <div className="max-h-[360px] overflow-y-auto">
                  {queue.map(({ card, quantity }, index) => {
                    const isProcessed = processedItems.has(card.id)
                    return (
                      <div
                        key={card.id}
                        className={`flex items-center gap-3 p-3 border-b border-surface-100 dark:border-surface-800 animate-fade-in ${isProcessed ? 'bg-green-50 dark:bg-green-900/20' : ''
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
                    )
                  })}
                </div>

                <div className="p-4 space-y-2 border-t border-surface-200 dark:border-surface-800">
                  <button
                    onClick={() => processMutation.mutate()}
                    disabled={processMutation.isPending || queue.every(item => processedItems.has(item.card.id))}
                    className={`btn w-full py-3 ${queue.every(item => processedItems.has(item.card.id))
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

      {/* Scan Results Modal */}
      {showScanModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeScanModal}
          />
          
          {/* Modal */}
          <div className="relative bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-white">
                {scanError ? 'Scan Result' : 'Card Detected'}
              </h3>
              <button
                onClick={closeScanModal}
                className="p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800"
              >
                <X size={20} />
              </button>
            </div>

            {/* Content */}
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {scanError ? (
                <div className="text-center py-8">
                  <AlertCircle size={48} className="mx-auto mb-4 text-yellow-500" />
                  <p className="text-surface-600 dark:text-surface-400">{scanError}</p>
                </div>
              ) : lastMatches.length > 0 ? (
                <>
                  {/* Best Match - Prominent */}
                  <div className="mb-4">
                    <p className="text-xs uppercase tracking-wide text-surface-500 mb-2">Best Match</p>
                    <div className="bg-gradient-to-br from-primary-50 to-primary-100 dark:from-primary-900/30 dark:to-primary-800/20 rounded-xl p-4 border border-primary-200 dark:border-primary-800">
                      <div className="flex gap-4">
                        <CardImage
                          productId={lastMatches[0].card_id}
                          alt={lastMatches[0].name}
                          size="image_256"
                          className="w-24 h-32 rounded-lg shadow-lg flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-lg text-surface-900 dark:text-white mb-1">
                            {lastMatches[0].name}
                          </h4>
                          <p className="text-surface-600 dark:text-surface-400 text-sm mb-1">
                            {lastMatches[0].set_name}
                          </p>
                          <p className="font-mono text-sm text-surface-500 mb-2">
                            {lastMatches[0].sku}
                          </p>
                          <div className="flex items-center gap-3 text-sm">
                            <span className="font-semibold text-surface-900 dark:text-white">
                              ${lastMatches[0].price.toFixed(2)}
                            </span>
                            <span className="text-surface-500">
                              Stock: {lastMatches[0].quantity}
                            </span>
                          </div>
                          <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 rounded-full text-xs font-medium">
                            <Check size={12} />
                            {(lastMatches[0].confidence * 100).toFixed(0)}% confidence
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => addMatchToQueue(lastMatches[0], true)}
                        className="btn btn-primary w-full mt-4"
                      >
                        <Plus size={18} />
                        Add to Queue
                      </button>
                    </div>
                  </div>

                  {/* Other Matches */}
                  {lastMatches.length > 1 && (
                    <div>
                      <p className="text-xs uppercase tracking-wide text-surface-500 mb-2">
                        Other Possible Matches
                      </p>
                      <div className="space-y-2">
                        {lastMatches.slice(1).map((match, index) => (
                          <div
                            key={index}
                            className="flex items-center gap-3 p-3 bg-surface-50 dark:bg-surface-800/50 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
                          >
                            <CardImage
                              productId={match.card_id}
                              alt={match.name}
                              size="image_128"
                              className="w-10 h-14 rounded flex-shrink-0"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="font-medium text-surface-900 dark:text-white truncate text-sm">
                                {match.name}
                              </div>
                              <div className="text-xs text-surface-500">
                                {match.set_name} • {(match.confidence * 100).toFixed(0)}%
                              </div>
                            </div>
                            <button
                              onClick={() => addMatchToQueue(match, true)}
                              className="btn btn-secondary p-2 text-sm"
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Processing time */}
                  {scanResult && (
                    <p className="text-xs text-surface-400 text-center mt-4">
                      Processed in {scanResult.processing_time_ms.toFixed(0)}ms
                    </p>
                  )}
                </>
              ) : null}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-surface-200 dark:border-surface-800 flex gap-3">
              {!scanError && lastMatches.length > 0 && (
                <button
                  onClick={closeScanModal}
                  className="btn btn-secondary flex-1"
                >
                  Not My Card
                </button>
              )}
              <button
                onClick={() => {
                  closeScanModal()
                  // Give a brief moment before allowing next scan
                  setTimeout(() => scanCurrentFrame(), 100)
                }}
                className="btn btn-ghost flex-1"
              >
                <RefreshCw size={16} />
                Scan Again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
