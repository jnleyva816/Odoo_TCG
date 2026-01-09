import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Loader2, Package, Search, X, Warehouse, Boxes } from 'lucide-react'
import { getInventory, getSets, Set } from '../api/client'
import CardImage from '../components/CardImage'
import CardModal from '../components/CardModal'
import { useAuth } from '../contexts/AuthContext'

type StockFilter = 'all' | 'in_stock' | 'out_of_stock'

// Component for each expandable set
function SetAccordion({ 
  set, 
  stockFilter,
  searchQuery,
  onCardClick 
}: { 
  set: Set
  stockFilter: StockFilter
  searchQuery: string
  onCardClick: (cardId: number) => void
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const { user } = useAuth()

  // Only fetch cards when expanded
  const { data: inventory, isLoading } = useQuery({
    queryKey: ['setInventory', set.id, stockFilter, searchQuery, user?.warehouse_id],
    queryFn: () => getInventory({
      set_id: set.id,
      stock: stockFilter,
      search: searchQuery || undefined,
      page: 1,
      page_size: 500, // Get all cards in set
      sort_by: 'sku',
      order: 'asc',
    }),
    enabled: isExpanded, // Only fetch when expanded
  })

  const cardCount = inventory?.total ?? set.card_count
  const inStockCount = inventory?.items.filter(c => c.quantity > 0).length ?? 0

  return (
    <div className="card overflow-hidden animate-fade-in">
      {/* Set Header - Clickable */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center gap-4 hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
      >
        {/* Expand Icon */}
        <div className="text-surface-400">
          {isExpanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
        </div>

        {/* Set Icon */}
        <div className="w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
          <Boxes className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        </div>

        {/* Set Info */}
        <div className="flex-1 text-left">
          <h3 className="font-semibold text-surface-900 dark:text-white">
            {set.name}
          </h3>
          <p className="text-sm text-surface-500">
            {cardCount} cards
            {isExpanded && inventory && (
              <span className="ml-2 text-green-500">
                • {inStockCount} in stock
              </span>
            )}
          </p>
        </div>

        {/* Stock Indicator */}
        {!isExpanded && (
          <div className="text-right">
            <span className="badge badge-outline">
              {set.card_count} cards
            </span>
          </div>
        )}
      </button>

      {/* Expanded Content - Cards Grid */}
      {isExpanded && (
        <div className="border-t border-surface-200 dark:border-surface-800 p-4 bg-surface-50 dark:bg-surface-950">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
            </div>
          ) : inventory?.items.length === 0 ? (
            <div className="text-center py-8 text-surface-500">
              <Package size={32} className="mx-auto mb-2 opacity-50" />
              <p>No cards match your filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
              {inventory?.items.map((card, index) => (
                <div
                  key={card.id}
                  onClick={() => onCardClick(card.id)}
                  className="cursor-pointer group animate-fade-in"
                  style={{ animationDelay: `${index * 15}ms` }}
                >
                  <div className="relative">
                    <CardImage
                      productId={card.id}
                      alt={card.name}
                      size="image_256"
                      className="aspect-[2.5/3.5] rounded-lg shadow-sm group-hover:shadow-md group-hover:scale-105 transition-all"
                    />
                    {/* Stock Badge */}
                    <div className={`absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-xs font-bold ${
                      card.quantity > 0 
                        ? 'bg-green-500 text-white' 
                        : 'bg-surface-800 text-surface-400'
                    }`}>
                      {card.quantity}
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-surface-600 dark:text-surface-400 truncate text-center">
                    {card.sku}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function InventoryPage() {
  const { currentWarehouse } = useAuth()
  const [searchQuery, setSearchQuery] = useState('')
  const [stockFilter, setStockFilter] = useState<StockFilter>('all')
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null)

  // Fetch all sets
  const { data: sets = [], isLoading: setsLoading } = useQuery({
    queryKey: ['sets'],
    queryFn: getSets,
  })

  // Filter sets based on search (optional - searches set names)
  const filteredSets = searchQuery
    ? sets.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : sets

  const clearSearch = () => {
    setSearchQuery('')
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 lg:py-8">
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
            <span className="text-sm text-surface-500">
              {sets.length} sets
            </span>
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6 animate-slide-in-up" style={{ animationDelay: '50ms' }}>
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search sets or cards..."
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

        {/* Stock Filter */}
        <select
          value={stockFilter}
          onChange={(e) => setStockFilter(e.target.value as StockFilter)}
          className="select"
        >
          <option value="all">All Stock</option>
          <option value="in_stock">In Stock Only</option>
          <option value="out_of_stock">Out of Stock</option>
        </select>
      </div>

      {/* Loading State */}
      {setsLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* Empty State */}
      {!setsLoading && filteredSets.length === 0 && (
        <div className="text-center py-24 text-surface-500">
          <Boxes size={64} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No sets found</p>
          {searchQuery && (
            <p className="text-sm">Try a different search term</p>
          )}
        </div>
      )}

      {/* Sets Accordion List */}
      {!setsLoading && filteredSets.length > 0 && (
        <div className="space-y-3">
          {filteredSets.map((set, index) => (
            <div key={set.id} style={{ animationDelay: `${index * 50}ms` }}>
              <SetAccordion
                set={set}
                stockFilter={stockFilter}
                searchQuery={searchQuery}
                onCardClick={setSelectedCardId}
              />
            </div>
          ))}
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
