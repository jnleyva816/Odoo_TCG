import { useState, useRef, useEffect } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutGrid, List, Loader2, Package, Search, X, ArrowLeft,
  ChevronDown, SortAsc, SortDesc, Warehouse, Layers
} from 'lucide-react'
import { getInventory, InventoryItem } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import CardImage from '../components/CardImage'
import CardModal from '../components/CardModal'

type ViewMode = 'grid' | 'list'
type SortField = 'sku' | 'name' | 'price' | 'quantity'
type SortDirection = 'asc' | 'desc'

// Helper to extract base card name (without variant suffix)
function getBaseName(name: string): string {
  const patterns = [
    /\s*\((Reverse Holo(?:foil)?)\)\s*$/i,
    /\s*\((Holo(?:foil)?)\)\s*$/i,
    /\s*\((Cosmos Holo)\)\s*$/i,
    /\s*-\s*(Reverse Holo(?:foil)?)\s*$/i,
    /\s*-\s*(Holo(?:foil)?)\s*$/i,
  ]

  let baseName = name
  for (const pattern of patterns) {
    baseName = baseName.replace(pattern, '')
  }
  return baseName.trim()
}

// Group cards by base name, keeping track of variant count
interface GroupedCard extends InventoryItem {
  variantCount: number
  totalQuantity: number
}

function groupCardsByBaseName(cards: InventoryItem[]): GroupedCard[] {
  const groups = new Map<string, InventoryItem[]>()

  for (const card of cards) {
    const baseName = getBaseName(card.name).toLowerCase()
    const key = `${card.set_name || ''}-${baseName}`

    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key)!.push(card)
  }

  // For each group, pick the "primary" card (normal version) and add variant info
  const result: GroupedCard[] = []

  for (const cards of groups.values()) {
    // Sort: Normal first, then by SKU
    cards.sort((a, b) => {
      const aIsNormal = getBaseName(a.name) === a.name
      const bIsNormal = getBaseName(b.name) === b.name
      if (aIsNormal && !bIsNormal) return -1
      if (!aIsNormal && bIsNormal) return 1
      return a.sku.localeCompare(b.sku)
    })

    const primary = cards[0]
    const totalQuantity = cards.reduce((sum, c) => sum + (c.quantity || 0), 0)

    result.push({
      ...primary,
      variantCount: cards.length,
      totalQuantity,
    })
  }

  return result
}

export default function SetDetailPage() {
  const { setId } = useParams<{ setId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const { currentWarehouse } = useAuth()

  const setName = (location.state as { setName?: string })?.setName || 'Set'

  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [sortField, setSortField] = useState<SortField>('sku')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null)

  const searchRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

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

  // Fetch all cards in this set
  const { data, isLoading, error } = useQuery({
    queryKey: ['set-cards', setId],
    queryFn: () => getInventory({
      page: 1,
      page_size: 500,
      set_id: setId ? parseInt(setId) : undefined,
    }),
    enabled: !!setId,
  })

  const cards = data?.items || []

  // Group cards by base name (removes variant duplicates)
  const groupedCards = groupCardsByBaseName(cards)

  // Filter by search
  const filteredCards = groupedCards.filter((card: GroupedCard) => {
    if (!debouncedSearch) return true
    const query = debouncedSearch.toLowerCase()
    return (
      card.name.toLowerCase().includes(query) ||
      card.sku.toLowerCase().includes(query)
    )
  })

  // Sort cards
  const sortedCards = [...filteredCards].sort((a: GroupedCard, b: GroupedCard) => {
    let comparison = 0
    switch (sortField) {
      case 'sku':
        comparison = a.sku.localeCompare(b.sku)
        break
      case 'name':
        comparison = a.name.localeCompare(b.name)
        break
      case 'price':
        comparison = parseFloat(a.price || '0') - parseFloat(b.price || '0')
        break
      case 'quantity':
        // Use total quantity across all variants
        comparison = (a.totalQuantity || 0) - (b.totalQuantity || 0)
        break
    }
    return sortDirection === 'asc' ? comparison : -comparison
  })

  const clearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    searchRef.current?.focus()
  }

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const handleCardClick = (card: GroupedCard) => {
    setSelectedCardId(card.id)
  }

  const SortIcon = sortDirection === 'asc' ? SortAsc : SortDesc

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 lg:py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 animate-slide-in-up">
        <div>
          <button
            onClick={() => navigate('/inventory')}
            className="flex items-center gap-2 text-surface-500 hover:text-primary-500 transition-colors mb-2"
          >
            <ArrowLeft size={18} />
            <span>Back to Sets</span>
          </button>
          <h1 className="text-2xl font-semibold text-surface-900 dark:text-white">
            {setName}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            {currentWarehouse && (
              <span className="badge badge-outline">
                <Warehouse size={12} className="mr-1.5" />
                {currentWarehouse.name}
              </span>
            )}
            <span className="text-sm text-surface-500">
              {sortedCards.length} cards
            </span>
          </div>
        </div>

        {/* View Toggle & Sort */}
        <div className="flex items-center gap-3">
          {/* Sort Dropdown */}
          <div className="relative">
            <select
              value={sortField}
              onChange={(e) => setSortField(e.target.value as SortField)}
              className="input pl-3 pr-8 py-2 text-sm appearance-none"
            >
              <option value="sku">Sort by SKU</option>
              <option value="name">Sort by Name</option>
              <option value="price">Sort by Price</option>
              <option value="quantity">Sort by Qty</option>
            </select>
            <ChevronDown size={16} className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none" />
          </div>

          {/* Sort Direction */}
          <button
            onClick={() => setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')}
            className="btn btn-outline p-2"
            title={sortDirection === 'asc' ? 'Ascending' : 'Descending'}
          >
            <SortIcon size={18} />
          </button>

          {/* View Toggle */}
          <div className="flex items-center bg-surface-100 dark:bg-surface-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-surface-700 shadow-sm text-surface-900 dark:text-white'
                  : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
              }`}
            >
              <LayoutGrid size={18} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-surface-700 shadow-sm text-surface-900 dark:text-white'
                  : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
              }`}
            >
              <List size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative mb-6 animate-slide-in-up" style={{ animationDelay: '50ms' }}>
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
        <input
          ref={searchRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search cards in this set..."
          className="input pl-12 pr-12 py-3 w-full"
          autoComplete="off"
        />
        {searchQuery && (
          <button
            onClick={clearSearch}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-400 hover:text-primary-500 transition-colors"
          >
            <X size={20} />
          </button>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card p-12 text-center">
          <Package size={48} className="mx-auto mb-4 text-red-400" />
          <h3 className="text-lg font-semibold text-surface-900 dark:text-white mb-2">Error loading cards</h3>
          <p className="text-surface-500">Please try again</p>
        </div>
      )}

      {/* Grid View */}
      {!isLoading && !error && viewMode === 'grid' && (
        <>
          {sortedCards.length === 0 ? (
            <div className="card p-12 text-center">
              <Package size={48} className="mx-auto mb-4 text-surface-400" />
              <h3 className="text-lg font-semibold text-surface-900 dark:text-white mb-2">
                {debouncedSearch ? 'No cards found' : 'No cards in this set'}
              </h3>
              <p className="text-surface-500">
                {debouncedSearch ? 'Try a different search term' : 'This set has no cards yet'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {sortedCards.map((card: GroupedCard, index: number) => {
                const inStock = card.totalQuantity > 0
                return (
                <div
                  key={card.id}
                  onClick={() => handleCardClick(card)}
                  className={`card p-3 cursor-pointer transition-all hover:shadow-soft-lg hover:-translate-y-1 animate-fade-in group ${
                    inStock
                      ? 'hover:border-primary-500/50 ring-2 ring-primary-500/20'
                      : 'opacity-60 hover:opacity-80'
                  }`}
                  style={{ animationDelay: `${Math.min(index * 15, 300)}ms` }}
                >
                  {/* Card Image */}
                  <div
                    className="aspect-[2.5/3.5] rounded-lg overflow-hidden mb-3"
                    style={!inStock ? { filter: 'saturate(0.3) brightness(0.7)' } : {}}
                  >
                    <CardImage
                      productId={card.id}
                      alt={card.name}
                      size="image_512"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  </div>

                  {/* Card Info */}
                  <div className="text-xs font-mono text-surface-500 truncate">{card.sku}</div>
                  <div className="text-sm font-medium text-surface-900 dark:text-white truncate mt-0.5">
                    {getBaseName(card.name)}
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="badge badge-sm badge-primary">
                      {card.totalQuantity}
                    </span>
                    <div className="flex items-center gap-1">
                      {card.variantCount > 1 && (
                        <span
                          className="flex items-center gap-0.5 text-[10px] text-surface-400"
                          title={`${card.variantCount} variants (Normal, Holo, etc.)`}
                        >
                          <Layers size={10} />
                          {card.variantCount}
                        </span>
                      )}
                      {parseFloat(card.price || '0') > 0 && (
                        <span className="text-xs font-semibold text-primary-600 dark:text-primary-400">
                          ${parseFloat(card.price).toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )})}

            </div>
          )}
        </>
      )}

      {/* List View */}
      {!isLoading && !error && viewMode === 'list' && (
        <>
          {sortedCards.length === 0 ? (
            <div className="card p-12 text-center">
              <Package size={48} className="mx-auto mb-4 text-surface-400" />
              <h3 className="text-lg font-semibold text-surface-900 dark:text-white mb-2">
                {debouncedSearch ? 'No cards found' : 'No cards in this set'}
              </h3>
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
                    <th className="w-16 px-4 py-3"></th>
                    <th
                      onClick={() => toggleSort('sku')}
                      className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider cursor-pointer hover:text-primary-500"
                    >
                      SKU {sortField === 'sku' && <SortIcon size={12} className="inline ml-1" />}
                    </th>
                    <th
                      onClick={() => toggleSort('name')}
                      className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider cursor-pointer hover:text-primary-500"
                    >
                      Name {sortField === 'name' && <SortIcon size={12} className="inline ml-1" />}
                    </th>
                    <th
                      onClick={() => toggleSort('quantity')}
                      className="px-4 py-3 text-right text-xs font-semibold text-surface-500 uppercase tracking-wider cursor-pointer hover:text-primary-500"
                    >
                      Qty {sortField === 'quantity' && <SortIcon size={12} className="inline ml-1" />}
                    </th>
                    <th
                      onClick={() => toggleSort('price')}
                      className="px-4 py-3 text-right text-xs font-semibold text-surface-500 uppercase tracking-wider cursor-pointer hover:text-primary-500"
                    >
                      Price {sortField === 'price' && <SortIcon size={12} className="inline ml-1" />}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                  {sortedCards.map((card: GroupedCard, index: number) => {
                    const inStock = card.totalQuantity > 0
                    return (
                    <tr
                      key={card.id}
                      onClick={() => handleCardClick(card)}
                      className={`cursor-pointer hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors animate-fade-in ${
                        !inStock ? 'opacity-50' : ''
                      }`}
                      style={{ animationDelay: `${Math.min(index * 10, 200)}ms` }}
                    >
                      <td className="px-4 py-3">
                        <div
                          className="w-10 h-14 rounded overflow-hidden"
                          style={!inStock ? { filter: 'saturate(0.3) brightness(0.7)' } : {}}
                        >
                          <CardImage
                            productId={card.id}
                            alt={card.name}
                            size="image_128"
                            className="w-full h-full object-cover"
                          />
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-sm text-surface-600 dark:text-surface-400">
                        {card.sku}
                      </td>
                      <td className="px-4 py-3 font-medium text-surface-900 dark:text-white">
                        <div className="flex items-center gap-2">
                          {getBaseName(card.name)}
                          {card.variantCount > 1 && (
                            <span
                              className="flex items-center gap-0.5 text-xs text-surface-400"
                              title={`${card.variantCount} variants (Normal, Holo, etc.)`}
                            >
                              <Layers size={12} />
                              {card.variantCount}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="badge badge-sm badge-primary">
                          {card.totalQuantity}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-primary-600 dark:text-primary-400">
                        {parseFloat(card.price || '0') > 0 ? `$${parseFloat(card.price).toFixed(2)}` : '-'}
                      </td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Card Modal */}
      {selectedCardId && (
        <CardModal
          cardId={selectedCardId}
          onClose={() => setSelectedCardId(null)}
        />
      )}
    </div>
  )
}
