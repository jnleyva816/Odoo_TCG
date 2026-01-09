/**
 * API client for the TCG backend
 */

const API_BASE = '/api'
const TOKEN_KEY = 'tcg_auth_token'

// Get auth headers
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY)
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

// Custom event for auth failure - AuthContext listens for this
const AUTH_FAILURE_EVENT = 'tcg:auth-failure'

export function dispatchAuthFailure() {
  window.dispatchEvent(new CustomEvent(AUTH_FAILURE_EVENT))
}

export function onAuthFailure(callback: () => void) {
  window.addEventListener(AUTH_FAILURE_EVENT, callback)
  return () => window.removeEventListener(AUTH_FAILURE_EVENT, callback)
}

// Fetch with auth - dispatches event on 401 instead of hard redirect
// This allows React components to handle auth state gracefully
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = {
    ...getAuthHeaders(),
    ...options.headers,
  }

  const res = await fetch(url, { ...options, headers })

  // On 401, dispatch event and clear token - let AuthContext handle redirect
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    dispatchAuthFailure()
  }

  return res
}

export interface Card {
  id: number
  sku: string
  name: string
  set_name: string | null
  quantity: number
  price: string
  has_image: boolean
}

export interface CardDetail extends Card {
  variant: string | null
  card_number: string | null
  rarity: string | null
  barcode: string | null
  image_url: string | null
}

export interface CardSearchResult {
  cards: Card[]
  total: number
  query: string
}

export interface InventoryItem extends Card {
  image_url: string
}

export interface InventoryResponse {
  items: InventoryItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SetInfo {
  id: number
  name: string
  card_count: number
}

export interface LabelResponse {
  success: boolean
  message: string
  pdf_base64: string | null
}

export interface PrinterStatus {
  enabled: boolean
  ip: string
  port: number
  model: string
  label_size: string
  connected: boolean
}

export interface PrintResponse {
  success: boolean
  message?: string
  error?: string
}

export interface SetInfo {
  code: string
  name: string
  series: string | null
  release_date: string | null
  card_count: number
  downloaded: boolean
  downloaded_count: number
  logo_url: string | null
}

export interface SetListResponse {
  sets: SetInfo[]
  total: number
}

export interface ImportStatus {
  status: 'queued' | 'importing' | 'complete' | 'error' | 'unknown'
  message: string
  created: number
  skipped: number
  errors: number
}

export interface Warehouse {
  id: number
  name: string
  code: string
}

export interface StockAdjustment {
  product_id: number
  quantity_change: number
  reason?: string
}

export interface StockAdjustmentResponse {
  success: boolean
  product_id: number
  new_quantity: number
  change: number
}

// Export for use in auth context
export const apiClient = {
  getAuthHeaders,
  authFetch,
}

// Search cards (uses Meilisearch for instant results)
export async function searchCards(query: string, limit = 50): Promise<CardSearchResult> {
  const params = new URLSearchParams({ q: query, page_size: String(limit) })
  // Use trailing slash to avoid 307 redirect which loses auth headers
  const res = await authFetch(`${API_BASE}/search/?${params}`)
  if (!res.ok) {
    // Fallback to old endpoint if new search fails
    const fallbackParams = new URLSearchParams({ q: query, limit: String(limit) })
    const fallbackRes = await authFetch(`${API_BASE}/cards/search?${fallbackParams}`)
    if (!fallbackRes.ok) throw new Error('Search failed')
    return fallbackRes.json()
  }
  const data = await res.json()
  // Transform to match old format
  return {
    cards: data.results,
    total: data.total,
    query: data.query,
  }
}

// Advanced search with all filters
export interface AdvancedSearchParams {
  q?: string
  set_id?: number
  stock?: 'all' | 'in_stock' | 'out_of_stock'
  sort_by?: 'sku' | 'name' | 'quantity' | 'price'
  order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface SearchResponse {
  query: string
  results: InventoryItem[]
  total: number
  page: number
  page_size: number
  source: 'meilisearch' | 'odoo'
}

export async function advancedSearch(params: AdvancedSearchParams): Promise<SearchResponse> {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q)
  if (params.set_id) searchParams.set('set_id', String(params.set_id))
  if (params.stock) searchParams.set('stock', params.stock)
  if (params.sort_by) searchParams.set('sort_by', params.sort_by)
  if (params.order) searchParams.set('order', params.order)
  if (params.page) searchParams.set('page', String(params.page))
  if (params.page_size) searchParams.set('page_size', String(params.page_size))

  // Use trailing slash to avoid 307 redirect which loses auth headers
  const res = await authFetch(`${API_BASE}/search/?${searchParams}`)
  if (!res.ok) throw new Error('Search failed')
  return res.json()
}

// Get card by ID
export async function getCard(cardId: number): Promise<CardDetail> {
  const res = await authFetch(`${API_BASE}/cards/${cardId}`)
  if (!res.ok) throw new Error('Card not found')
  return res.json()
}

// Get card by SKU
export async function getCardBySku(sku: string): Promise<CardDetail> {
  const res = await authFetch(`${API_BASE}/cards/sku/${encodeURIComponent(sku)}`)
  if (!res.ok) throw new Error('Card not found')
  return res.json()
}

// Get all sets
export async function getSets(): Promise<SetInfo[]> {
  const res = await authFetch(`${API_BASE}/cards/sets/`)
  if (!res.ok) throw new Error('Failed to fetch sets')
  return res.json()
}

// Get inventory
export async function getInventory(params: {
  search?: string
  set_id?: number
  stock?: 'all' | 'in_stock' | 'out_of_stock'
  sort_by?: 'sku' | 'name' | 'quantity' | 'price' | 'recent'
  order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}): Promise<InventoryResponse> {
  const searchParams = new URLSearchParams()
  if (params.search) searchParams.set('search', params.search)
  if (params.set_id) searchParams.set('set_id', String(params.set_id))
  if (params.stock) searchParams.set('stock', params.stock)
  if (params.sort_by) searchParams.set('sort_by', params.sort_by)
  if (params.order) searchParams.set('order', params.order)
  if (params.page) searchParams.set('page', String(params.page))
  if (params.page_size) searchParams.set('page_size', String(params.page_size))

  const res = await authFetch(`${API_BASE}/inventory/?${searchParams}`)
  if (!res.ok) throw new Error('Failed to fetch inventory')
  return res.json()
}

// Adjust stock
export async function adjustStock(adjustment: StockAdjustment): Promise<StockAdjustmentResponse> {
  const res = await authFetch(`${API_BASE}/inventory/adjust`, {
    method: 'POST',
    body: JSON.stringify(adjustment),
  })
  if (!res.ok) throw new Error('Failed to adjust stock')
  return res.json()
}

// Generate label
export async function generateLabel(productId: number, quantity = 1): Promise<LabelResponse> {
  const res = await authFetch(`${API_BASE}/labels/generate`, {
    method: 'POST',
    body: JSON.stringify({ product_id: productId, quantity }),
  })
  if (!res.ok) throw new Error('Failed to generate label')
  return res.json()
}

// Preview label
export async function previewLabel(productId: number): Promise<LabelResponse> {
  const res = await authFetch(`${API_BASE}/labels/preview/${productId}`)
  if (!res.ok) throw new Error('Failed to preview label')
  return res.json()
}

// Get printer status
export async function getPrinterStatus(): Promise<PrinterStatus> {
  const res = await authFetch(`${API_BASE}/labels/printer/status`)
  if (!res.ok) throw new Error('Failed to get printer status')
  return res.json()
}

// Print label directly to printer
export async function printLabel(productId: number): Promise<PrintResponse> {
  const res = await authFetch(`${API_BASE}/labels/print/${productId}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to print label')
  return res.json()
}

// Get image URL (includes auth token as query param for <img> tags)
export function getImageUrl(productId: number, size: 'image_128' | 'image_256' | 'image_512' | 'image_1920' = 'image_256'): string {
  const token = localStorage.getItem(TOKEN_KEY)
  const baseUrl = `${API_BASE}/images/${productId}?size=${size}`
  return token ? `${baseUrl}&token=${token}` : baseUrl
}

// Get printer label preview URL
export function getPrinterPreviewUrl(productId: number): string {
  const token = localStorage.getItem(TOKEN_KEY)
  const baseUrl = `${API_BASE}/labels/printer/preview/${productId}`
  return token ? `${baseUrl}?token=${token}` : baseUrl
}

// Health check (public endpoint)
export async function healthCheck(): Promise<{ status: string; odoo_connected: boolean; version: string }> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

// Get available warehouses for current user
export async function getWarehouses(): Promise<Warehouse[]> {
  const res = await authFetch(`${API_BASE}/auth/warehouses`)
  if (!res.ok) throw new Error('Failed to fetch warehouses')
  return res.json()
}

// Switch active warehouse (admin only)
export async function switchWarehouse(warehouseId: number): Promise<{ success: boolean; warehouse_id: number; new_token: string }> {
  const res = await authFetch(`${API_BASE}/auth/switch-warehouse`, {
    method: 'POST',
    body: JSON.stringify({ warehouse_id: warehouseId }),
  })
  if (!res.ok) throw new Error('Failed to switch warehouse')
  return res.json()
}

// Get available sets
export async function getAvailableSets(params?: {
  search?: string
  show_downloaded?: boolean
}): Promise<SetListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.search) searchParams.set('search', params.search)
  if (params?.show_downloaded) searchParams.set('show_downloaded', 'true')
  
  const res = await authFetch(`${API_BASE}/sets/available?${searchParams}`)
  if (!res.ok) throw new Error('Failed to fetch sets')
  return res.json()
}

// Import a set
export async function importSet(params: {
  set_code: string
  skip_images?: boolean
}): Promise<{ success: boolean; message: string; set_code: string; status: string }> {
  const res = await authFetch(`${API_BASE}/sets/import`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error('Failed to start import')
  return res.json()
}

// Get import status
export async function getImportStatus(setCode: string): Promise<ImportStatus> {
  const res = await authFetch(`${API_BASE}/sets/status/${setCode}`)
  if (!res.ok) throw new Error('Failed to get import status')
  return res.json()
}
