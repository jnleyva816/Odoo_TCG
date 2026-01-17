import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { LayoutGrid, List, Loader2, Package, Search, X, Warehouse, Layers } from 'lucide-react'
import { getSets, searchCards } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import CardImage from '../components/CardImage'
import CardModal from '../components/CardModal'

type ViewMode = 'grid' | 'list'

export default function InventoryPage() {
  const navigate = useNavigate()
  const { currentWarehouse } = useAuth()
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
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

  // Fetch all sets
  const { data: sets = [], isLoading: setsLoading } = useQuery({
    queryKey: ['sets'],
    queryFn: getSets,
  })

  // Search cards when searching
  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['card-search', debouncedSearch],
    queryFn: () => searchCards(debouncedSearch, 100),
    enabled: debouncedSearch.length >= 2,
  })

  const clearSearch = () => {
    setSearchQuery('')
    setDebouncedSearch('')
    searchRef.current?.focus()
  }

  const isSearching = debouncedSearch.length >= 2

  const handleSetClick = (setId: number, setName: string) => {
    navigate(`/inventory/set/${setId}`, { state: { setName } })
  }

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
            <span className="text-sm text-surface-500">
              {sets.length} sets
            </span>
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
      <div className="relative mb-6 animate-slide-in-up" style={{ animationDelay: '50ms' }}>
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-surface-400" size={20} />
        <input
          ref={searchRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search cards across all sets..."
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

      {/* Loading */}
      {(setsLoading || (isSearching && searchLoading)) && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
        </div>
      )}

      {/* Search Results */}
      {isSearching && !searchLoading && (
        <>
          {searchResults?.cards.length === 0 ? (
            <div className="card p-12 text-center">
              <Package size={48} className="mx-auto mb-4 text-surface-400" />
              <h3 className="text-lg font-semibold text-surface-900 dark:text-white mb-2">No cards found</h3>
              <p className="text-surface-500">Try a different search term</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-surface-500 mb-4">
                Found {searchResults?.total} cards matching "{debouncedSearch}"
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {searchResults?.cards.map((card, index) => (
                  <div
                    key={card.id}
                    className="card p-3 cursor-pointer transition-all hover:shadow-soft-lg hover:border-primary-500/50 hover:-translate-y-1 animate-fade-in group"
                    style={{ animationDelay: `${index * 15}ms` }}
                    onClick={() => setSelectedCardId(card.id)}
                  >
                    <div className="aspect-[2.5/3.5] rounded-lg overflow-hidden mb-3">
                      <CardImage
                        productId={card.id}
                        alt={card.name}
                        size="image_512"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    </div>
                    <div>
                      <div className="text-xs font-mono text-surface-500 truncate">{card.sku}</div>
                      <div className="text-sm font-medium text-surface-900 dark:text-white truncate">{card.name}</div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="badge badge-sm badge-primary">
                          Qty: {card.quantity}
                        </span>
                        <span className="text-xs text-surface-500">{card.set_name}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Sets Display (when not searching) */}
      {!isSearching && !setsLoading && (
        <>
          {/* Grid View */}
          {viewMode === 'grid' && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {sets.map((set, index) => (
                <div
                  key={set.id}
                  onClick={() => handleSetClick(set.id, set.name)}
                  className="card p-4 cursor-pointer transition-all hover:shadow-soft-lg hover:border-primary-500/50 hover:-translate-y-1 animate-fade-in group"
                  style={{ animationDelay: `${index * 30}ms` }}
                >
                  {/* Set Icon/Logo */}
                  <div className="aspect-square bg-gradient-to-br from-primary-500/10 to-primary-600/20 rounded-xl flex items-center justify-center mb-4 group-hover:from-primary-500/20 group-hover:to-primary-600/30 transition-colors overflow-hidden">
                    {set.logo_url ? (
                      <img 
                        src={set.logo_url} 
                        alt={set.name}
                        className="w-full h-full object-contain p-2"
                        onError={(e) => {
                          // Fallback to icon on error
                          e.currentTarget.style.display = 'none'
                          e.currentTarget.nextElementSibling?.classList.remove('hidden')
                        }}
                      />
                    ) : null}
                    <Layers size={48} className={`text-primary-500 ${set.logo_url ? 'hidden' : ''}`} />
                  </div>

                  {/* Set Info */}
                  <h3 className="font-semibold text-surface-900 dark:text-white truncate text-center">
                    {set.name}
                  </h3>
                  <p className="text-sm text-surface-500 text-center mt-1">
                    {set.card_count} cards
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* List View */}
          {viewMode === 'list' && (
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-surface-500 uppercase tracking-wider">
                      Set
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-surface-500 uppercase tracking-wider">
                      Cards
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                  {sets.map((set, index) => (
                    <tr
                      key={set.id}
                      onClick={() => handleSetClick(set.id, set.name)}
                      className="cursor-pointer hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors animate-fade-in"
                      style={{ animationDelay: `${index * 20}ms` }}
                    >
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 bg-gradient-to-br from-primary-500/10 to-primary-600/20 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden">
                            {set.logo_url ? (
                              <img 
                                src={set.logo_url} 
                                alt={set.name}
                                className="w-full h-full object-contain p-1"
                                onError={(e) => {
                                  e.currentTarget.style.display = 'none'
                                  e.currentTarget.nextElementSibling?.classList.remove('hidden')
                                }}
                              />
                            ) : null}
                            <Layers size={24} className={`text-primary-500 ${set.logo_url ? 'hidden' : ''}`} />
                          </div>
                          <span className="font-medium text-surface-900 dark:text-white">
                            {set.name}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <span className="badge badge-outline">
                          {set.card_count} cards
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Empty State */}
      {!isSearching && !setsLoading && sets.length === 0 && (
        <div className="card p-12 text-center">
          <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500/20 to-primary-600/20 flex items-center justify-center">
            <Package size={40} className="text-primary-500" />
          </div>
          <h3 className="text-xl font-semibold text-surface-900 dark:text-white mb-2">
            No sets found
          </h3>
          <p className="text-surface-500">
            Import some card sets to get started
          </p>
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
