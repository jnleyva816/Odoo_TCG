import { useState, useRef, useEffect, useCallback } from 'react'
import { X, Camera, Loader2, Zap, RefreshCw, AlertCircle, Upload } from 'lucide-react'

interface ScannerModalProps {
  isOpen: boolean
  onClose: () => void
  onCapture: (imageData: string) => Promise<void>
  scanning: boolean
}

type PermissionState = 'prompt' | 'granted' | 'denied' | 'unknown'

export default function ScannerModal({ isOpen, onClose, onCapture, scanning }: ScannerModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [cameraReady, setCameraReady] = useState(false)
  const [permissionState, setPermissionState] = useState<PermissionState>('unknown')
  const [error, setError] = useState<string | null>(null)
  const [autoScan, setAutoScan] = useState(false)
  const autoScanRef = useRef<ReturnType<typeof setInterval>>()

  // Card frame dimensions (2.5:3.5 aspect ratio - standard trading card)
  const CARD_ASPECT_RATIO = 2.5 / 3.5

  // Check camera permission status
  const checkPermission = useCallback(async () => {
    try {
      // Try Permissions API first (not supported in all browsers)
      if (navigator.permissions && navigator.permissions.query) {
        try {
          const result = await navigator.permissions.query({ name: 'camera' as PermissionName })
          setPermissionState(result.state as PermissionState)

          result.addEventListener('change', () => {
            setPermissionState(result.state as PermissionState)
          })
          return result.state
        } catch {
          // Permissions API doesn't support camera query in this browser
        }
      }
      return 'unknown'
    } catch {
      return 'unknown'
    }
  }, [])

  // Start camera stream
  const startCamera = useCallback(async () => {
    setError(null)
    setCameraReady(false)

    try {
      // Stop any existing stream first
      if (stream) {
        stream.getTracks().forEach(track => track.stop())
        setStream(null)
      }

      // Mobile-optimized constraints
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: 'environment' }, // Back camera on mobile
          width: { ideal: 1920, min: 640 },
          height: { ideal: 1080, min: 480 },
        },
        audio: false,
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints)

      if (!videoRef.current) {
        mediaStream.getTracks().forEach(track => track.stop())
        return
      }

      setStream(mediaStream)
      videoRef.current.srcObject = mediaStream
      setPermissionState('granted')

      // Wait for video to be ready
      await new Promise<void>((resolve, reject) => {
        const video = videoRef.current!

        const handleLoadedMetadata = () => {
          video.removeEventListener('loadedmetadata', handleLoadedMetadata)
          video.removeEventListener('error', handleError)
          video.play()
            .then(() => {
              setTimeout(() => {
                if (video.videoWidth > 0 && video.videoHeight > 0) {
                  resolve()
                } else {
                  reject(new Error('Video has no dimensions'))
                }
              }, 100)
            })
            .catch(reject)
        }

        const handleError = () => {
          video.removeEventListener('loadedmetadata', handleLoadedMetadata)
          video.removeEventListener('error', handleError)
          reject(new Error('Video element error'))
        }

        video.addEventListener('loadedmetadata', handleLoadedMetadata)
        video.addEventListener('error', handleError)

        // Timeout fallback
        setTimeout(() => {
          video.removeEventListener('loadedmetadata', handleLoadedMetadata)
          video.removeEventListener('error', handleError)
          if (video.videoWidth > 0) {
            resolve()
          } else {
            reject(new Error('Video initialization timeout'))
          }
        }, 5000)
      })

      setCameraReady(true)
    } catch (err) {
      console.error('Camera access error:', err)

      if (err instanceof Error) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setPermissionState('denied')
          setError('Camera permission denied. Please allow camera access in your browser settings.')
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setError('No camera found on this device.')
        } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
          setError('Camera is in use by another application. Please close other apps using the camera.')
        } else if (err.name === 'OverconstrainedError') {
          // Try with simpler constraints
          try {
            const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
            if (videoRef.current) {
              setStream(fallbackStream)
              videoRef.current.srcObject = fallbackStream
              await videoRef.current.play()
              setCameraReady(true)
              setPermissionState('granted')
              return
            }
          } catch {
            setError('Camera constraints could not be satisfied.')
          }
        } else {
          setError(`Camera error: ${err.message}`)
        }
      } else {
        setError('Failed to access camera. Please check permissions.')
      }
    }
  }, [stream])

  // Stop camera
  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop())
      setStream(null)
    }
    setCameraReady(false)
    setAutoScan(false)
    if (autoScanRef.current) {
      clearInterval(autoScanRef.current)
    }
  }, [stream])

  // Capture frame with card region
  const captureFrame = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current || !cameraReady) return null

    const video = videoRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    // Set canvas to full video dimensions
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    // Draw the full frame
    ctx.drawImage(video, 0, 0)

    return canvas.toDataURL('image/jpeg', 0.85)
  }, [cameraReady])

  // Handle scan button click
  const handleScan = useCallback(async () => {
    const imageData = captureFrame()
    if (imageData) {
      await onCapture(imageData)
    }
  }, [captureFrame, onCapture])

  // Handle file upload
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async (event) => {
      const imageData = event.target?.result as string
      if (imageData) {
        await onCapture(imageData)
      }
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }, [onCapture])

  // Toggle auto scan
  const toggleAutoScan = useCallback(() => {
    if (autoScan) {
      setAutoScan(false)
      if (autoScanRef.current) {
        clearInterval(autoScanRef.current)
      }
    } else {
      setAutoScan(true)
      autoScanRef.current = setInterval(() => {
        handleScan()
      }, 1500)
    }
  }, [autoScan, handleScan])

  // Draw blur overlay around card frame
  const drawOverlay = useCallback(() => {
    if (!overlayCanvasRef.current || !videoRef.current || !cameraReady) return

    const canvas = overlayCanvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height

    // Calculate card frame dimensions (80% of the smaller dimension)
    const frameHeight = height * 0.7
    const frameWidth = frameHeight * CARD_ASPECT_RATIO
    const frameX = (width - frameWidth) / 2
    const frameY = (height - frameHeight) / 2

    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Draw semi-transparent overlay everywhere
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
    ctx.fillRect(0, 0, width, height)

    // Cut out the card frame area (make it transparent)
    ctx.globalCompositeOperation = 'destination-out'
    ctx.fillStyle = 'rgba(0, 0, 0, 1)'

    // Rounded rectangle for the card frame
    const radius = 12
    ctx.beginPath()
    ctx.moveTo(frameX + radius, frameY)
    ctx.lineTo(frameX + frameWidth - radius, frameY)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY, frameX + frameWidth, frameY + radius)
    ctx.lineTo(frameX + frameWidth, frameY + frameHeight - radius)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY + frameHeight, frameX + frameWidth - radius, frameY + frameHeight)
    ctx.lineTo(frameX + radius, frameY + frameHeight)
    ctx.quadraticCurveTo(frameX, frameY + frameHeight, frameX, frameY + frameHeight - radius)
    ctx.lineTo(frameX, frameY + radius)
    ctx.quadraticCurveTo(frameX, frameY, frameX + radius, frameY)
    ctx.closePath()
    ctx.fill()

    // Reset composite operation
    ctx.globalCompositeOperation = 'source-over'

    // Draw card frame border
    ctx.strokeStyle = scanning ? 'rgba(250, 204, 21, 0.9)' : 'rgba(255, 255, 255, 0.8)'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(frameX + radius, frameY)
    ctx.lineTo(frameX + frameWidth - radius, frameY)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY, frameX + frameWidth, frameY + radius)
    ctx.lineTo(frameX + frameWidth, frameY + frameHeight - radius)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY + frameHeight, frameX + frameWidth - radius, frameY + frameHeight)
    ctx.lineTo(frameX + radius, frameY + frameHeight)
    ctx.quadraticCurveTo(frameX, frameY + frameHeight, frameX, frameY + frameHeight - radius)
    ctx.lineTo(frameX, frameY + radius)
    ctx.quadraticCurveTo(frameX, frameY, frameX + radius, frameY)
    ctx.closePath()
    ctx.stroke()

    // Draw corner accents
    const cornerLength = 20
    const cornerWidth = 4
    ctx.strokeStyle = scanning ? '#facc15' : '#ffffff'
    ctx.lineWidth = cornerWidth
    ctx.lineCap = 'round'

    // Top-left corner
    ctx.beginPath()
    ctx.moveTo(frameX, frameY + cornerLength)
    ctx.lineTo(frameX, frameY + radius)
    ctx.quadraticCurveTo(frameX, frameY, frameX + radius, frameY)
    ctx.lineTo(frameX + cornerLength, frameY)
    ctx.stroke()

    // Top-right corner
    ctx.beginPath()
    ctx.moveTo(frameX + frameWidth - cornerLength, frameY)
    ctx.lineTo(frameX + frameWidth - radius, frameY)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY, frameX + frameWidth, frameY + radius)
    ctx.lineTo(frameX + frameWidth, frameY + cornerLength)
    ctx.stroke()

    // Bottom-left corner
    ctx.beginPath()
    ctx.moveTo(frameX, frameY + frameHeight - cornerLength)
    ctx.lineTo(frameX, frameY + frameHeight - radius)
    ctx.quadraticCurveTo(frameX, frameY + frameHeight, frameX + radius, frameY + frameHeight)
    ctx.lineTo(frameX + cornerLength, frameY + frameHeight)
    ctx.stroke()

    // Bottom-right corner
    ctx.beginPath()
    ctx.moveTo(frameX + frameWidth - cornerLength, frameY + frameHeight)
    ctx.lineTo(frameX + frameWidth - radius, frameY + frameHeight)
    ctx.quadraticCurveTo(frameX + frameWidth, frameY + frameHeight, frameX + frameWidth, frameY + frameHeight - radius)
    ctx.lineTo(frameX + frameWidth, frameY + frameHeight - cornerLength)
    ctx.stroke()

  }, [cameraReady, scanning, CARD_ASPECT_RATIO])

  // Initialize on open
  useEffect(() => {
    if (isOpen) {
      checkPermission().then((state) => {
        if (state !== 'denied') {
          startCamera()
        }
      })
    } else {
      stopCamera()
    }

    return () => {
      stopCamera()
    }
  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  // Redraw overlay on resize or when camera/scanning state changes
  useEffect(() => {
    if (!isOpen || !cameraReady) return

    drawOverlay()

    const handleResize = () => drawOverlay()
    window.addEventListener('resize', handleResize)

    // Redraw periodically to keep overlay in sync
    const intervalId = setInterval(drawOverlay, 100)

    return () => {
      window.removeEventListener('resize', handleResize)
      clearInterval(intervalId)
    }
  }, [isOpen, cameraReady, scanning, drawOverlay])

  // Cleanup auto-scan on unmount
  useEffect(() => {
    return () => {
      if (autoScanRef.current) {
        clearInterval(autoScanRef.current)
      }
    }
  }, [])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[100] bg-black">
      {/* Hidden elements */}
      <canvas ref={canvasRef} className="hidden" />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-20 p-4 bg-gradient-to-b from-black/80 to-transparent">
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold text-lg">Scan Card</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
          >
            <X size={24} className="text-white" />
          </button>
        </div>
      </div>

      {/* Camera View */}
      <div className="absolute inset-0">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />

        {/* Overlay canvas for blur effect and frame */}
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />

        {/* Instructions */}
        {cameraReady && (
          <div className="absolute top-20 left-0 right-0 text-center pointer-events-none">
            <p className="text-white/90 text-sm font-medium bg-black/40 inline-block px-4 py-2 rounded-full">
              Position card within the frame
            </p>
          </div>
        )}

        {/* Scanning indicator */}
        {scanning && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-black/60 rounded-2xl p-6 flex flex-col items-center gap-3">
              <Loader2 size={40} className="text-yellow-400 animate-spin" />
              <span className="text-white font-medium">Scanning...</span>
            </div>
          </div>
        )}
      </div>

      {/* Permission Denied / Error State */}
      {(permissionState === 'denied' || error) && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/90 z-30">
          <div className="text-center p-6 max-w-sm">
            <AlertCircle size={64} className="mx-auto mb-4 text-red-400" />
            <h3 className="text-white text-xl font-semibold mb-2">
              {permissionState === 'denied' ? 'Camera Access Denied' : 'Camera Error'}
            </h3>
            <p className="text-white/70 mb-6">
              {error || 'Please allow camera access in your browser settings to scan cards.'}
            </p>
            <div className="space-y-3">
              <button
                onClick={startCamera}
                className="w-full py-3 px-6 bg-white text-black rounded-xl font-medium hover:bg-white/90 transition-colors flex items-center justify-center gap-2"
              >
                <RefreshCw size={18} />
                Try Again
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full py-3 px-6 bg-white/20 text-white rounded-xl font-medium hover:bg-white/30 transition-colors flex items-center justify-center gap-2"
              >
                <Upload size={18} />
                Upload Image Instead
              </button>
              <button
                onClick={onClose}
                className="w-full py-3 px-6 text-white/70 hover:text-white transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {!cameraReady && !error && permissionState !== 'denied' && (
        <div className="absolute inset-0 flex items-center justify-center bg-black z-30">
          <div className="text-center">
            <Loader2 size={48} className="mx-auto mb-4 text-white animate-spin" />
            <p className="text-white/70">Starting camera...</p>
          </div>
        </div>
      )}

      {/* Bottom Controls */}
      {cameraReady && (
        <div className="absolute bottom-0 left-0 right-0 z-20 p-6 pb-safe bg-gradient-to-t from-black/80 to-transparent">
          <div className="flex items-center justify-center gap-4">
            {/* Upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-4 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              disabled={scanning}
            >
              <Upload size={24} className="text-white" />
            </button>

            {/* Main scan button */}
            <button
              onClick={handleScan}
              disabled={scanning}
              className="w-20 h-20 rounded-full bg-white flex items-center justify-center hover:bg-white/90 transition-colors disabled:opacity-50 shadow-lg"
            >
              {scanning ? (
                <Loader2 size={36} className="text-black animate-spin" />
              ) : (
                <Camera size={36} className="text-black" />
              )}
            </button>

            {/* Auto-scan toggle */}
            <button
              onClick={toggleAutoScan}
              className={`p-4 rounded-full transition-colors ${
                autoScan
                  ? 'bg-yellow-500 hover:bg-yellow-400'
                  : 'bg-white/20 hover:bg-white/30'
              }`}
              disabled={scanning}
            >
              <Zap size={24} className={autoScan ? 'text-black' : 'text-white'} />
            </button>
          </div>

          {/* Auto-scan indicator */}
          {autoScan && (
            <p className="text-center text-yellow-400 text-sm mt-3 font-medium">
              Auto-scan active
            </p>
          )}
        </div>
      )}
    </div>
  )
}
