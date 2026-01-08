import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LayoutGrid, List, ChevronLeft, ChevronRight, Loader2, Package, Filter, Search, X, Warehouse } from 'lucide-react'
import { getInventory, getSets } from '../api/client'
import CardImage from '../components/CardImage'
import CardModal from '../components/CardModal'
import { useAuth } from '../contexts/AuthContext'

type ViewMode = 'grid' | 'list'
type StockFilter = 'all' | 'in_stock' | 'out_of_stock'
type SortField = 'sku' | 'name' | 'quantity' | 'price'
type SortOrder = 'asc' | 'desc'

export default function InventoryPage() {
  const { currentWarehouse, user } = useAuth()
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedSet, setSelectedSet] = useState<number | undefined>()
  const [stockFilter, setStockFilter] = useState<StockFilter>('all')
  const [sortBy, setSortBy] = useState<SortField>('sku')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [page, setPage] = useState(1)
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const pageSize = 24

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

  // Fetch sets for filter
  const { data: sets = [] } = useQuery({
    queryKey: ['sets'],
    queryFn: getSets,
  })

  // Fetch inventory - includes warehouse_id in cache key so it refetches on switch
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

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-3xl font-bold text-surface-900 dark:text-white">
            Inventory
          </h1>
          <div className="flex items-center gap-2 mt-1">
            {currentWarehouse && (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-sm">
                <Warehouse size={14} />
                {currentWarehouse.name}
              </span>
            )}
            <span className="text-surface-500">
              {inventory?.total ?? 0} cards
            </span>
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-2 bg-surface-100 dark:bg-surface-800 rounded-lg p-1">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded-md transition-colors ${
              viewMode === 'grid'
                ? 'bg-white dark:bg-surface-700 shadow-sm'
                : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
            }`}
          >
            <LayoutGrid size={20} />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded-md transition-colors ${
              viewMode === 'list'
                ? 'bg-white dark:bg-surface-700 shadow-sm'
                : 'text-surface-500 hover:text-surface-700 dark:hover:text-surface-300'
            }`}
          >
            <List size={20} />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
        <input
          ref={searchRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by name or SKU..."
          className="input pl-12 pr-12 py-3"
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

      {/* Filters */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter size={18} className="text-surface-500" />
            <span className="text-sm font-medium text-surface-600 dark:text-surface-400">Filters:</span>
          </div>

          {/* Set Filter */}
          <select
            value={selectedSet || ''}
            onChange={(e) => handleSetChange(e.target.value)}
            className="select text-sm"
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
              setStockFilter(e.target.value as StockFilter)
              setPage(1)
            }}
            className="select text-sm"
          >
            <option value="all">All Stock</option>
            <option value="in_stock">In Stock</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>

          {/* Sort */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-sm text-surface-500">Sort:</span>
            {(['sku', 'name', 'quantity', 'price'] as SortField[]).map((field) => (
              <button
                key={field}
                onClick={() => handleSortChange(field)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  sortBy === field
                    ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                    : 'text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800'
                }`}
              >
                {field.charAt(0).toUpperCase() + field.slice(1)}
                {sortBy === field && (
                  <span className="ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && inventory?.items.length === 0 && (
        <div className="text-center py-24 text-surface-500">
          <Package size={64} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No cards found</p>
          <p className="text-sm">Try adjusting your filters or search</p>
        </div>
      )}

      {/* Grid View */}
      {!isLoading && viewMode === 'grid' && inventory && inventory.items.length > 0 && (
        <div className={`grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 ${isFetching ? 'opacity-70' : ''}`}>
          {inventory.items.map((item, index) => (
            <div
              key={item.id}
              className="card p-3 cursor-pointer hover:border-primary-500 hover:shadow-md transition-all animate-fade-in"
              style={{ animationDelay: `${index * 20}ms` }}
              onClick={() => setSelectedCardId(item.id)}
            >
              <CardImage
                productId={item.id}
                alt={item.name}
                size="image_256"
                className="aspect-[2.5/3.5] rounded-lg mb-3"
              />
              <div className="text-xs font-mono text-surface-500 truncate">
                {item.sku}
              </div>
              <div className="text-sm font-medium text-surface-900 dark:text-white truncate">
                {item.name}
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className={`text-sm font-medium ${
                  item.quantity > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                }`}>
                  {item.quantity} in stock
                </span>
                <span className="text-sm font-bold text-surface-900 dark:text-white">
                  ${parseFloat(item.price).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* List View */}
      {!isLoading && viewMode === 'list' && inventory && inventory.items.length > 0 && (
        <div className={`card overflow-hidden ${isFetching ? 'opacity-70' : ''}`}>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800">
                <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 uppercase tracking-wider">
                  Card
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 uppercase tracking-wider">
                  SKU
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-surface-500 uppercase tracking-wider">
                  Set
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-surface-500 uppercase tracking-wider">
                  Stock
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-surface-500 uppercase tracking-wider">
                  Price
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
              {inventory.items.map((item, index) => (
                <tr
                  key={item.id}
                  className="hover:bg-surface-50 dark:hover:bg-surface-800 cursor-pointer transition-colors animate-fade-in"
                  style={{ animationDelay: `${index * 15}ms` }}
                  onClick={() => setSelectedCardId(item.id)}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <CardImage
                        productId={item.id}
                        alt={item.name}
                        size="image_128"
                        className="w-10 h-14 rounded flex-shrink-0"
                      />
                      <span className="font-medium text-surface-900 dark:text-white">
                        {item.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-sm text-surface-500">
                    {item.sku}
                  </td>
                  <td className="px-4 py-3 text-sm text-surface-500">
                    {item.set_name || 'N/A'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-medium ${
                      item.quantity > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    }`}>
                      {item.quantity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-surface-900 dark:text-white">
                    ${parseFloat(item.price).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {inventory && inventory.total_pages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page === 1}
            className="btn btn-secondary"
          >
            <ChevronLeft size={18} />
            Previous
          </button>
          
          <span className="text-sm text-surface-600 dark:text-surface-400">
            Page {page} of {inventory.total_pages}
          </span>
          
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= inventory.total_pages}
            className="btn btn-secondary"
          >
            Next
            <ChevronRight size={18} />
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
