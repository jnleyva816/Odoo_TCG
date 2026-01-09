import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LayoutGrid, List, ChevronLeft, ChevronRight, Loader2, Package, Search, X, Warehouse, Filter, ArrowUpDown } from 'lucide-react'
import { getInventory, getSets } from '../api/client'
import CardImage from '../components/CardImage'
import CardModal from '../components/CardModal'
import { useAuth } from '../contexts/AuthContext'

type ViewMode = 'grid' | 'list'
type StockFilter = 'all' | 'in_stock' | 'out_of_stock'
type SortField = 'sku' | 'name' | 'quantity' | 'price' | 'recent'
type SortOrder = 'asc' | 'desc'

export default function InventoryPage() {
  const { currentWarehouse, user } = useAuth()
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedSet, setSelectedSet] = useState<number | undefined>()
  const [stockFilter, setStockFilter] = useState<StockFilter>('all')
  const [showAll, setShowAll] = useState(false)
  const [sortBy, setSortBy] = useState<SortField>('sku')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [page, setPage] = useState(1)
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const pageSize = 48

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setPage(1)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchQuery])

  // Fetch sets for dropdown
  const { data: sets = [] } = useQuery({
    queryKey: ['sets'],
    queryFn: getSets,
  })

  // Only fetch inventory when there's a search query OR a selected set OR showAll is enabled
  const shouldFetch = debouncedSearch.length >= 2 || selectedSet !== undefined || showAll

  const { data: inventory, isLoading, isFetching } = useQuery({
    queryKey: ['inventory', debouncedSearch, selectedSet, stockFilter, sortBy, sortOrder, page, pageSize, user?.warehouse_id],
    queryFn: () => getInventory({
      search: debouncedSearch || undefined,
      set_id: selectedSet,
      stock: stockFilter,
      sort_by: sortBy,
      order: sortOrder,
      page,
      page_size: pageSize,
    }),
    enabled: shouldFetch,
    placeholderData: (prev) => prev,
  })

  const handleSetChange = (setId: string) => {
    setSelectedSet(setId ? parseInt(setId) : undefined)
    setPage(1)
  }

  const handleSortChange = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
    setPage(1)
  }

  const clearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    searchRef.current?.focus()
  }

  const clearFilters = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    setSelectedSet(undefined)
    setStockFilter('all')
    setShowAll(false)
    setPage(1)
  }

  // Get selected set name for display
  const selectedSetName = selectedSet ? sets.find(s => s.id === selectedSet)?.name : null

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 lg:py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 animate-slide-in-up">
        <div>
          <h1 className="text-2xl font-semibold text-surface-900 dark:text-white">
            Inventory
          </h1>
          <div className="flex items-center gap-3 mt-1">
            {currentWarehouse && (
              <span className="badge badge-outline">
                <Warehouse size={12} className="mr-1.5" />
                {currentWarehouse.name}
              </span>
            )}
            {shouldFetch && inventory && (
              <span className="text-sm text-surface-500">
                {inventory.total.toLocaleString()} cards
              </span>
            )}
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-2">
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
      <div className="relative mb-4 animate-slide-in-up" style={{ animationDelay: '50ms' }}>
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
        <input
          ref={searchRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by name or SKU..."
          className="input pl-12 pr-12 py-3 w-full text-lg"
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

      {/* Filters Card */}
      <div className="card p-4 mb-6 animate-slide-in-up" style={{ animationDelay: '100ms' }}>
        <div className="flex flex-wrap items-center gap-4">
          {/* Filter Icon */}
          <div className="flex items-center gap-2 text-surface-500">
            <Filter size={16} />
            <span className="text-sm font-medium">Filters</span>
          </div>

          {/* Set Dropdown */}
          <select
            value={selectedSet || ''}
            onChange={(e) => handleSetChange(e.target.value)}
            className="select"
          >
            <option value="">All Sets</option>
            {sets.map((set) => (
              <option key={set.id} value={set.id}>
                {set.name} ({set.card_count})
              </option>
            ))}
          </select>

          {/* Stock Filter */}
          <select
            value={stockFilter}
            onChange={(e) => {
              const newFilter = e.target.value as StockFilter
              setStockFilter(newFilter)
              // Reset sort if switching away from in_stock and was sorting by recent
              if (newFilter !== 'in_stock' && sortBy === 'recent') {
                setSortBy('sku')
              }
              setPage(1)
            }}
            className="select"
          >
            <option value="all">All Stock</option>
            <option value="in_stock">In Stock</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>

          {/* Show All Toggle */}
          <button
            onClick={() => {
              setShowAll(!showAll)
              setPage(1)
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              showAll
                ? 'bg-primary-500 text-white'
                : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
            }`}
          >
            {showAll ? '✓ Show All' : 'Show All'}
          </button>

          {/* Sort Options */}
          <div className="flex items-center gap-2 ml-auto">
            <ArrowUpDown size={16} className="text-surface-500" />
            <span className="text-sm text-surface-500 hidden sm:inline">Sort:</span>
            {(['sku', 'name', 'quantity', 'price', ...(stockFilter === 'in_stock' ? ['recent'] : [])] as SortField[]).map((field) => (
              <button
                key={field}
                onClick={() => handleSortChange(field)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  sortBy === field
                    ? 'bg-primary-500 text-white'
                    : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
                }`}
              >
                {field === 'quantity' ? 'Qty' : field === 'recent' ? 'Recent' : field.charAt(0).toUpperCase() + field.slice(1)}
                {sortBy === field && (
                  <span className="ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Active Filters / Selected Set Display */}
      {(selectedSetName || stockFilter !== 'all' || showAll) && (
        <div className="flex flex-wrap items-center gap-2 mb-4 animate-fade-in">
          {showAll && (
            <span className="badge badge-primary">
              Showing All Cards
              <button onClick={() => setShowAll(false)} className="ml-1 hover:text-white/80">
                <X size={14} />
              </button>
            </span>
          )}
          {selectedSetName && (
            <span className="badge badge-primary">
              {selectedSetName}
              <button onClick={() => setSelectedSet(undefined)} className="ml-1 hover:text-white/80">
                <X size={14} />
              </button>
            </span>
          )}
          {stockFilter !== 'all' && (
            <span className="badge badge-outline">
              {stockFilter === 'in_stock' ? 'In Stock' : 'Out of Stock'}
              <button onClick={() => setStockFilter('all')} className="ml-1 hover:text-primary-500">
                <X size={14} />
              </button>
            </span>
          )}
          <button onClick={clearFilters} className="text-sm text-surface-500 hover:text-primary-500 ml-2">
            Clear all
          </button>
        </div>
      )}

      {/* Empty State - No search or set selected */}
      {!shouldFetch && (
        <div className="card p-12 text-center animate-fade-in">
          <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500/20 to-primary-600/20 flex items-center justify-center">
            <Package size={40} className="text-primary-500" />
          </div>
          <h3 className="text-xl font-semibold text-surface-900 dark:text-white mb-2">
            Search for cards or select a set
          </h3>
          <p className="text-surface-500 max-w-md mx-auto">
            Type at least 2 characters to search, or choose a set from the dropdown above to browse cards.
          </p>
        </div>
      )}

      {/* Loading */}
      {shouldFetch && isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* No Results */}
      {shouldFetch && !isLoading && inventory?.items.length === 0 && (
        <div className="card p-12 text-center">
          <Package size={48} className="mx-auto mb-4 text-surface-400" />
          <h3 className="text-lg font-semibold text-surface-900 dark:text-white mb-2">No cards found</h3>
          <p className="text-surface-500 mb-4">Try adjusting your filters or search term</p>
          <button onClick={clearFilters} className="btn btn-secondary">
            Clear Filters
          </button>
        </div>
      )}

      {/* Grid View */}
      {shouldFetch && !isLoading && viewMode === 'grid' && inventory && inventory.items.length > 0 && (
        <div className={`grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 ${isFetching ? 'opacity-70' : ''}`}>
          {inventory.items.map((item, index) => {
            const inStock = item.quantity > 0
            return (
              <div
                key={item.id}
                className={`card p-3 cursor-pointer transition-all animate-fade-in hover:shadow-soft-lg ${
                  inStock 
                    ? 'hover:border-primary-500/50 hover:-translate-y-1' 
                    : 'opacity-60 hover:opacity-80'
                }`}
                style={{ animationDelay: `${index * 15}ms` }}
                onClick={() => setSelectedCardId(item.id)}
              >
                <div className="relative">
                  <CardImage
                    productId={item.id}
                    alt={item.name}
                    size="image_256"
                    className={`aspect-[2.5/3.5] rounded-lg ${!inStock ? 'saturate-50' : ''}`}
                  />
                  {/* Stock Badge */}
                  <div className={`absolute bottom-2 right-2 px-2 py-1 rounded-md text-xs font-bold shadow-sm ${
                    inStock
                      ? 'bg-green-500 text-white'
                      : 'bg-surface-800/80 text-surface-300'
                  }`}>
                    {item.quantity} {inStock ? 'in stock' : ''}
                  </div>
                </div>
                <div className="mt-3">
                  <div className="text-xs font-mono text-surface-500 truncate">
                    {item.sku}
                  </div>
                  <div className={`text-sm font-medium truncate ${inStock ? 'text-surface-900 dark:text-white' : 'text-surface-500'}`}>
                    {item.name}
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className={`text-sm font-semibold ${inStock ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400'}`}>
                      ${parseFloat(item.price).toFixed(2)}
                    </span>
                    {item.set_name && (
                      <span className="text-xs text-surface-400 truncate max-w-[80px]">
                        {item.set_name}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* List View */}
      {shouldFetch && !isLoading && viewMode === 'list' && inventory && inventory.items.length > 0 && (
        <div className={`card overflow-hidden ${isFetching ? 'opacity-70' : ''}`}>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
                <th className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider">
                  Card
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider hidden sm:table-cell">
                  SKU
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider hidden md:table-cell">
                  Set
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-surface-500 uppercase tracking-wider">
                  Stock
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-surface-500 uppercase tracking-wider">
                  Price
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
              {inventory.items.map((item, index) => {
                const inStock = item.quantity > 0
                return (
                  <tr
                    key={item.id}
                    className={`cursor-pointer transition-all animate-fade-in ${
                      inStock
                        ? 'hover:bg-surface-50 dark:hover:bg-surface-800/50'
                        : 'opacity-50 hover:opacity-70 bg-surface-50/50 dark:bg-surface-900/50'
                    }`}
                    style={{ animationDelay: `${index * 10}ms` }}
                    onClick={() => setSelectedCardId(item.id)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <CardImage
                          productId={item.id}
                          alt={item.name}
                          size="image_128"
                          className={`w-10 h-14 rounded flex-shrink-0 ${!inStock ? 'saturate-50' : ''}`}
                        />
                        <span className={`font-medium ${inStock ? 'text-surface-900 dark:text-white' : 'text-surface-500'}`}>
                          {item.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-sm text-surface-500 hidden sm:table-cell">
                      {item.sku}
                    </td>
                    <td className="px-4 py-3 text-sm text-surface-500 hidden md:table-cell">
                      {item.set_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`inline-flex items-center px-2 py-1 rounded-md text-sm font-semibold ${
                        inStock 
                          ? 'bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400' 
                          : 'bg-surface-100 dark:bg-surface-800 text-surface-400'
                      }`}>
                        {item.quantity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-surface-900 dark:text-white">
                      ${parseFloat(item.price).toFixed(2)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {shouldFetch && inventory && inventory.total_pages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-8 animate-fade-in">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page === 1}
            className="btn btn-secondary"
          >
            <ChevronLeft size={16} />
            Previous
          </button>
          
          <div className="flex items-center gap-2">
            <span className="text-sm text-surface-500">
              Page
            </span>
            <span className="px-3 py-1 bg-surface-100 dark:bg-surface-800 rounded-lg font-medium">
              {page}
            </span>
            <span className="text-sm text-surface-500">
              of {inventory.total_pages}
            </span>
          </div>
          
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= inventory.total_pages}
            className="btn btn-secondary"
          >
            Next
            <ChevronRight size={16} />
          </button>
        </div>
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
