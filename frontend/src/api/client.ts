/**
 * API client for the TCG backend
 */

const API_BASE = '/api'

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

// Search cards
export async function searchCards(query: string, limit = 50): Promise<CardSearchResult> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  const res = await fetch(`${API_BASE}/cards/search?${params}`)
  if (!res.ok) throw new Error('Search failed')
  return res.json()
}

// Get card by ID
export async function getCard(cardId: number): Promise<CardDetail> {
  const res = await fetch(`${API_BASE}/cards/${cardId}`)
  if (!res.ok) throw new Error('Card not found')
  return res.json()
}

// Get card by SKU
export async function getCardBySku(sku: string): Promise<CardDetail> {
  const res = await fetch(`${API_BASE}/cards/sku/${encodeURIComponent(sku)}`)
  if (!res.ok) throw new Error('Card not found')
  return res.json()
}

// Get all sets
export async function getSets(): Promise<SetInfo[]> {
  const res = await fetch(`${API_BASE}/cards/sets/`)
  if (!res.ok) throw new Error('Failed to fetch sets')
  return res.json()
}

// Get inventory
export async function getInventory(params: {
  search?: string
  set_id?: number
  stock?: 'all' | 'in_stock' | 'out_of_stock'
  sort_by?: 'sku' | 'name' | 'quantity' | 'price'
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

  const res = await fetch(`${API_BASE}/inventory/?${searchParams}`)
  if (!res.ok) throw new Error('Failed to fetch inventory')
  return res.json()
}

// Adjust stock
export async function adjustStock(adjustment: StockAdjustment): Promise<StockAdjustmentResponse> {
  const res = await fetch(`${API_BASE}/inventory/adjust`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(adjustment),
  })
  if (!res.ok) throw new Error('Failed to adjust stock')
  return res.json()
}

// Generate label
export async function generateLabel(productId: number, quantity = 1): Promise<LabelResponse> {
  const res = await fetch(`${API_BASE}/labels/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, quantity }),
  })
  if (!res.ok) throw new Error('Failed to generate label')
  return res.json()
}

// Preview label
export async function previewLabel(productId: number): Promise<LabelResponse> {
  const res = await fetch(`${API_BASE}/labels/preview/${productId}`)
  if (!res.ok) throw new Error('Failed to preview label')
  return res.json()
}

// Get printer status
export async function getPrinterStatus(): Promise<PrinterStatus> {
  const res = await fetch(`${API_BASE}/labels/printer/status`)
  if (!res.ok) throw new Error('Failed to get printer status')
  return res.json()
}

// Print label directly to printer
export async function printLabel(productId: number): Promise<PrintResponse> {
  const res = await fetch(`${API_BASE}/labels/print/${productId}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to print label')
  return res.json()
}

// Get image URL
export function getImageUrl(productId: number, size: 'image_128' | 'image_256' | 'image_512' | 'image_1920' = 'image_256'): string {
  return `${API_BASE}/images/${productId}?size=${size}`
}

// Get printer label preview URL (returns PNG image URL)
export function getPrinterPreviewUrl(productId: number): string {
  return `${API_BASE}/labels/printer/preview/${productId}`
}

// Health check
export async function healthCheck(): Promise<{ status: string; odoo_connected: boolean; version: string }> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Health check failed')
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
  
  const res = await fetch(`${API_BASE}/sets/available?${searchParams}`)
  if (!res.ok) throw new Error('Failed to fetch sets')
  return res.json()
}

// Import a set
export async function importSet(params: {
  set_code: string
  skip_images?: boolean
}): Promise<{ success: boolean; message: string; set_code: string; status: string }> {
  const res = await fetch(`${API_BASE}/sets/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error('Failed to start import')
  return res.json()
}

// Get import status
export async function getImportStatus(setCode: string): Promise<ImportStatus> {
  const res = await fetch(`${API_BASE}/sets/status/${setCode}`)
  if (!res.ok) throw new Error('Failed to get import status')
  return res.json()
}

