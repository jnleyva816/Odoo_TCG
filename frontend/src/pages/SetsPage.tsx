import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Download, Check, Loader2, X, Database, Clock, RefreshCw } from 'lucide-react'
import { getAvailableSets, importSet, getImportStatus } from '../api/client'

interface SetInfo {
  code: string
  name: string
  series: string | null
  release_date: string | null
  card_count: number
  downloaded: boolean
  downloaded_count: number
  logo_url: string | null
}

interface ImportStatus {
  status: string
  message: string
  created: number
  skipped: number
  errors: number
}

export default function SetsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [showDownloaded, setShowDownloaded] = useState(false)
  const [importingSet, setImportingSet] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const queryClient = useQueryClient()

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(searchQuery)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchQuery])

  // Fetch sets
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['available-sets', debouncedSearch, showDownloaded],
    queryFn: () => getAvailableSets({ search: debouncedSearch || undefined, show_downloaded: showDownloaded }),
  })

  // Poll import status
  const { data: importStatus } = useQuery<ImportStatus | null>({
    queryKey: ['import-status', importingSet],
    queryFn: async () => {
      if (!importingSet) return null
      return getImportStatus(importingSet) as Promise<ImportStatus>
    },
    enabled: !!importingSet,
    refetchInterval: importingSet ? 2000 : false,
  })

  // Handle import completion
  useEffect(() => {
    if (importStatus?.status === 'complete' || importStatus?.status === 'error') {
      setTimeout(() => {
        setImportingSet(null)
        queryClient.invalidateQueries({ queryKey: ['available-sets'] })
      }, 3000)
    }
  }, [importStatus, queryClient])

  // Import mutation
  const importMutation = useMutation({
    mutationFn: importSet,
    onSuccess: (_, variables) => {
      setImportingSet(variables.set_code)
    },
  })

  const handleImport = (setCode: string) => {
    importMutation.mutate({ set_code: setCode })
  }

  const clearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    searchRef.current?.focus()
  }

  const getStatusBadge = (set: SetInfo) => {
    if (importingSet === set.code) {
      if (importStatus?.status === 'importing') {
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs">
            <Loader2 size={12} className="animate-spin" />
            {importStatus.message?.includes('/') ? importStatus.message.split(':')[0] : 'Importing...'}
          </span>
        )
      }
      if (importStatus?.status === 'complete') {
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-xs">
            <Check size={12} />
            +{importStatus.created} cards
          </span>
        )
      }
      if (importStatus?.status === 'error') {
        return (
          <span className="flex items-center gap-1 px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-full text-xs" title={importStatus.message}>
            <X size={12} />
            Error
          </span>
        )
      }
      return (
        <span className="flex items-center gap-1 px-2 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded-full text-xs">
          <Clock size={12} />
          Queued
        </span>
      )
    }

    if (set.downloaded) {
      return (
        <span className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-xs">
          <Check size={12} />
          {set.downloaded_count} cards
        </span>
      )
    }

    return null
  }

  // Group sets by series
  const groupedSets = data?.sets?.reduce((acc, set) => {
    const series = set.series || 'Other'
    if (!acc[series]) acc[series] = []
    acc[series].push(set)
    return acc
  }, {} as Record<string, SetInfo[]>) || {}

  const seriesOrder = Object.keys(groupedSets).sort((a, b) => {
    // Put newer series first
    const aDate = groupedSets[a][0]?.release_date || ''
    const bDate = groupedSets[b][0]?.release_date || ''
    return bDate.localeCompare(aDate)
  })

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-bold text-surface-900 dark:text-white">
            Card Sets
          </h1>
          <p className="text-surface-500 mt-1">
            {data?.total ?? 0} sets available from TCGdex
          </p>
        </div>
        <button 
          onClick={() => refetch()}
          className="btn btn-secondary"
          disabled={isLoading}
        >
          <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
          <input
            ref={searchRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search sets by name, code, or series..."
            className="input pl-12 pr-12 py-3 w-full"
            autoComplete="off"
          />
          {searchQuery && (
            <button
              onClick={clearSearch}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
            >
              <X size={20} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDownloaded(false)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              !showDownloaded
                ? 'bg-primary-600 text-white'
                : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400'
            }`}
          >
            All Sets
          </button>
          <button
            onClick={() => setShowDownloaded(true)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              showDownloaded
                ? 'bg-primary-600 text-white'
                : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400'
            }`}
          >
            Downloaded
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="card p-6 text-center text-red-500 mb-6">
          <p>Failed to load sets. Please try again.</p>
          <button onClick={() => refetch()} className="btn btn-secondary mt-4">
            <RefreshCw size={18} />
            Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && data?.sets?.length === 0 && (
        <div className="text-center py-24 text-surface-500">
          <Database size={64} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No sets found</p>
          <p className="text-sm">Try adjusting your search</p>
        </div>
      )}

      {/* Sets grouped by Series */}
      {!isLoading && !error && seriesOrder.map((series) => (
        <div key={series} className="mb-8">
          <h2 className="font-display font-bold text-lg text-surface-700 dark:text-surface-300 mb-3 sticky top-0 bg-surface-50 dark:bg-surface-950 py-2 z-10">
            {series}
            <span className="text-sm font-normal text-surface-500 ml-2">
              ({groupedSets[series].length} sets)
            </span>
          </h2>
          
          <div className="space-y-2">
            {groupedSets[series].map((set, index) => (
              <div
                key={set.code}
                className="card p-3 flex items-center gap-3 animate-fade-in hover:border-primary-500/50 transition-colors"
                style={{ animationDelay: `${index * 20}ms` }}
              >
                {/* Set Logo/Code Badge */}
                {set.logo_url ? (
                  <img 
                    src={set.logo_url} 
                    alt={set.name}
                    className="w-12 h-12 object-contain flex-shrink-0"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none'
                    }}
                  />
                ) : (
                  <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center flex-shrink-0">
                    <span className="font-display font-bold text-white text-xs uppercase">
                      {set.code.slice(0, 4)}
                    </span>
                  </div>
                )}

                {/* Set Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-medium text-surface-900 dark:text-white truncate">
                      {set.name}
                    </h3>
                    {getStatusBadge(set)}
                  </div>
                  <p className="text-xs text-surface-500">
                    {set.code.toUpperCase()} • {set.card_count} cards
                    {set.release_date && ` • ${set.release_date}`}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex-shrink-0">
                  {set.downloaded ? (
                    <button
                      onClick={() => handleImport(set.code)}
                      disabled={importingSet === set.code}
                      className="btn btn-ghost text-sm px-3 py-1.5"
                      title="Re-download set"
                    >
                      <RefreshCw size={16} />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleImport(set.code)}
                      disabled={importingSet === set.code || importMutation.isPending}
                      className="btn btn-primary text-sm px-3 py-1.5"
                    >
                      {importingSet === set.code ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <Download size={16} />
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Import Status Toast */}
      {importingSet && importStatus && (
        <div className="fixed bottom-4 right-4 card p-4 shadow-lg max-w-sm animate-slide-up z-50">
          <div className="flex items-start gap-3">
            {importStatus.status === 'importing' && (
              <Loader2 className="w-5 h-5 animate-spin text-blue-500 flex-shrink-0 mt-0.5" />
            )}
            {importStatus.status === 'complete' && (
              <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
            )}
            {importStatus.status === 'error' && (
              <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            )}
            {importStatus.status === 'queued' && (
              <Clock className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-surface-900 dark:text-white">
                {importStatus.status === 'importing' && 'Importing...'}
                {importStatus.status === 'complete' && 'Import Complete!'}
                {importStatus.status === 'error' && 'Import Failed'}
                {importStatus.status === 'queued' && 'Queued...'}
              </p>
              <p className="text-sm text-surface-500 truncate">
                {importStatus.message}
              </p>
              {importStatus.status === 'complete' && (
                <p className="text-xs text-surface-400 mt-1">
                  Created: {importStatus.created} • Skipped: {importStatus.skipped}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
