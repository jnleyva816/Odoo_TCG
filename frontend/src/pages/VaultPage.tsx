/**
 * Digital Vault Page - Public collection showcase
 * 
 * Features:
 * - Create/manage "binders" of cards
 * - Publish to shareable public URLs
 * - Visitors can browse without authentication
 */

import { useEffect, useState } from 'react';
import { useFeatures } from '../contexts/FeaturesContext';

const TOKEN_KEY = 'tcg_auth_token';

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY);
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
}

interface VaultListItem {
  id: string;
  name: string;
  visibility: 'private' | 'unlisted' | 'public';
  card_count: number;
  total_value: string | null;
  view_count: number;
  updated_at: string;
  public_url: string | null;
}

export default function VaultPage() {
  const { features } = useFeatures();
  const [vaults, setVaults] = useState<VaultListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newVaultName, setNewVaultName] = useState('');

  useEffect(() => {
    async function fetchVaults() {
      try {
        const response = await fetch('/api/vault/my-vaults', { headers: getAuthHeaders() });
        if (!response.ok) throw new Error('Failed to load vaults');
        const data = await response.json();
        setVaults(data);
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load vaults';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    }

    if (features.public_vault) {
      fetchVaults();
    }
  }, [features.public_vault]);

  const handleCreateVault = async () => {
    if (!newVaultName.trim()) return;

    try {
      const response = await fetch('/api/vault/', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name: newVaultName,
          visibility: 'unlisted',
          settings: {
            show_prices: true,
            show_quantities: true,
          },
          product_ids: [],
        }),
      });
      if (!response.ok) throw new Error('Failed');
      const data = await response.json();
      setVaults([...vaults, data]);
      setNewVaultName('');
      setShowCreateModal(false);
    } catch (err) {
      console.error('Failed to create vault:', err);
    }
  };

  const handlePublish = async (vaultId: string) => {
    try {
      const response = await fetch(`/api/vault/${vaultId}/publish`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed');
      const data = await response.json();
      // Update the vault in the list with the new public URL
      setVaults(vaults.map(v => 
        v.id === vaultId 
          ? { ...v, public_url: data.public_url, visibility: 'unlisted' as const }
          : v
      ));
      // Copy URL to clipboard
      navigator.clipboard.writeText(window.location.origin + data.public_url);
      alert('Published! URL copied to clipboard.');
    } catch (err) {
      console.error('Failed to publish vault:', err);
    }
  };

  const handleDelete = async (vaultId: string) => {
    if (!confirm('Are you sure you want to delete this vault?')) return;

    try {
      const response = await fetch(`/api/vault/${vaultId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed');
      setVaults(vaults.filter(v => v.id !== vaultId));
    } catch (err) {
      console.error('Failed to delete vault:', err);
    }
  };

  if (!features.public_vault) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-gray-400">Digital Vault</h1>
        <p className="mt-4 text-gray-500">This feature is not enabled.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-red-500">Error</h1>
        <p className="mt-4 text-gray-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Digital Vault</h1>
          <p className="text-gray-400 mt-1">
            Create shareable binders of your collection
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors"
        >
          + New Vault
        </button>
      </div>

      {/* Vaults List */}
      {vaults.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-12 text-center">
          <div className="text-6xl mb-4">🗄️</div>
          <h2 className="text-xl font-semibold text-white mb-2">No Vaults Yet</h2>
          <p className="text-gray-400 mb-6">
            Create a vault to start showcasing your collection
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors"
          >
            Create Your First Vault
          </button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {vaults.map((vault) => (
            <div
              key={vault.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-lg font-semibold text-white">{vault.name}</h3>
                <span className={`px-2 py-1 text-xs rounded ${
                  vault.visibility === 'public' 
                    ? 'bg-green-500/20 text-green-400'
                    : vault.visibility === 'unlisted'
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-gray-500/20 text-gray-400'
                }`}>
                  {vault.visibility}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center mb-4">
                <div>
                  <p className="text-2xl font-bold text-white">{vault.card_count}</p>
                  <p className="text-gray-500 text-xs">Cards</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">
                    {vault.total_value ? `$${vault.total_value}` : '-'}
                  </p>
                  <p className="text-gray-500 text-xs">Value</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{vault.view_count}</p>
                  <p className="text-gray-500 text-xs">Views</p>
                </div>
              </div>

              <div className="flex gap-2">
                {vault.public_url ? (
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(window.location.origin + vault.public_url);
                      alert('URL copied!');
                    }}
                    className="flex-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white text-sm rounded transition-colors"
                  >
                    Copy Link
                  </button>
                ) : (
                  <button
                    onClick={() => handlePublish(vault.id)}
                    className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded transition-colors"
                  >
                    Publish
                  </button>
                )}
                <button
                  onClick={() => handleDelete(vault.id)}
                  className="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 text-sm rounded transition-colors"
                >
                  Delete
                </button>
              </div>

              <p className="text-gray-600 text-xs mt-3">
                Updated {new Date(vault.updated_at).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-semibold text-white mb-4">Create New Vault</h2>
            <input
              type="text"
              value={newVaultName}
              onChange={(e) => setNewVaultName(e.target.value)}
              placeholder="Vault name (e.g., 'High-End Trades')"
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-red-500"
              autoFocus
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateVault}
                disabled={!newVaultName.trim()}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

