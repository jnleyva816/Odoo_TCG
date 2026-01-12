import { useState, useEffect } from 'react';
import {
  Printer,
  Warehouse,
  User,
  Download,
  Check,
  X,
  RefreshCw,
  Smartphone,
  Monitor,
  ToggleLeft,
  ToggleRight,
  Settings2,
  RotateCcw,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useFeatures } from '../contexts/FeaturesContext';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

interface FeatureFlags {
  scanner_page: boolean;
  inventory_page: boolean;
  sets_page: boolean;
  label_printing: boolean;
  portfolio_dashboard: boolean;
  public_vault: boolean;
}

const FEATURE_INFO: Record<keyof FeatureFlags, { name: string; description: string; category: 'core' | 'premium' }> = {
  scanner_page: { name: 'Barcode Scanner', description: 'Quick inventory via barcode scanning', category: 'core' },
  inventory_page: { name: 'Inventory Page', description: 'Full inventory management view', category: 'core' },
  sets_page: { name: 'Card Sets', description: 'Import and manage card sets', category: 'core' },
  label_printing: { name: 'Label Printing', description: 'Print labels via Brother QL printer', category: 'core' },
  portfolio_dashboard: { name: 'Portfolio Dashboard', description: '"Wall Street" style analytics', category: 'premium' },
  public_vault: { name: 'Digital Vault', description: 'Public collection showcase', category: 'premium' },
};

export default function SettingsPage() {
  const { user, warehouses, currentWarehouse, switchWarehouse, canSwitchWarehouse } = useAuth();
  const { features } = useFeatures();
  const [printerStatus, setPrinterStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  // Feature flag management
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags | null>(null);
  const [featureLoading, setFeatureLoading] = useState<string | null>(null);
  const [featureError, setFeatureError] = useState<string | null>(null);

  const printerEnabled = features.label_printing;
  const isAdmin = user?.role === 'admin';

  // Fetch feature flags for admin
  useEffect(() => {
    if (isAdmin) {
      fetch('/api/settings/features', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('tcg_auth_token')}` }
      })
        .then(res => res.ok ? res.json() : Promise.reject('Failed'))
        .then(data => setFeatureFlags(data))
        .catch(() => setFeatureFlags(features as FeatureFlags));
    }
  }, [isAdmin, features]);

  useEffect(() => {
    const checkPrinter = async () => {
      if (printerEnabled) {
        try {
          const res = await fetch('/api/labels/status');
          setPrinterStatus(res.ok ? 'connected' : 'disconnected');
        } catch {
          setPrinterStatus('disconnected');
        }
      } else {
        setPrinterStatus('disconnected');
      }
    };
    checkPrinter();
  }, [printerEnabled]);

  useEffect(() => {
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
      return;
    }

    setIsIOS(/iPad|iPhone|iPod/.test(navigator.userAgent));

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setIsInstalled(true);
    }
    setDeferredPrompt(null);
  };

  const refreshPrinterStatus = async () => {
    setPrinterStatus('checking');
    try {
      const res = await fetch('/api/labels/status');
      setPrinterStatus(res.ok ? 'connected' : 'disconnected');
    } catch {
      setPrinterStatus('disconnected');
    }
  };

  const toggleFeature = async (featureName: keyof FeatureFlags) => {
    if (!featureFlags) return;
    
    setFeatureLoading(featureName);
    setFeatureError(null);

    const newValue = !featureFlags[featureName];

    try {
      const res = await fetch(`/api/settings/features/${featureName}?enabled=${newValue}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('tcg_auth_token')}` }
      });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setFeatureFlags(data);
      // Force page reload to update all components
      window.location.reload();
    } catch (err) {
      setFeatureError(`Failed to toggle ${featureName}`);
      console.error(err);
    } finally {
      setFeatureLoading(null);
    }
  };

  const resetToDefaults = async () => {
    if (!confirm('Reset all settings to environment defaults?')) return;

    setFeatureLoading('reset');
    try {
      const res = await fetch('/api/settings/reset', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('tcg_auth_token')}` }
      });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setFeatureFlags(data.features);
      window.location.reload();
    } catch (err) {
      setFeatureError('Failed to reset settings');
      console.error(err);
    } finally {
      setFeatureLoading(null);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-surface-900 dark:text-white mb-6 animate-slide-in-up">
        Settings
      </h1>

      <div className="space-y-4">
        {/* Printer Section */}
        <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '50ms' }}>
          <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-50 dark:bg-orange-500/10 rounded-xl flex items-center justify-center">
              <Printer className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">Label Printer</h2>
              <p className="text-sm text-surface-500">Brother QL-800</p>
            </div>
          </div>
          
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-surface-600 dark:text-surface-400">Feature Enabled</span>
              <span className={`badge ${printerEnabled ? 'badge-success' : 'badge-outline'}`}>
                {printerEnabled ? <><Check className="w-3 h-3 mr-1" /> Yes</> : <><X className="w-3 h-3 mr-1" /> No</>}
              </span>
            </div>
            
            <div className="divider" />
            
            <div className="flex items-center justify-between">
              <span className="text-surface-600 dark:text-surface-400">Connection</span>
              <div className="flex items-center gap-2">
                {printerStatus === 'checking' ? (
                  <span className="badge badge-outline">
                    <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> Checking
                  </span>
                ) : printerStatus === 'connected' ? (
                  <span className="badge badge-success">
                    <Check className="w-3 h-3 mr-1" /> Connected
                  </span>
                ) : (
                  <span className="badge badge-error">
                    <X className="w-3 h-3 mr-1" /> Offline
                  </span>
                )}
                <button
                  onClick={refreshPrinterStatus}
                  className="p-2 text-surface-400 hover:text-primary-500 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Warehouse Section */}
        <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '100ms' }}>
          <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 dark:bg-blue-500/10 rounded-xl flex items-center justify-center">
              <Warehouse className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">Warehouse</h2>
              <p className="text-sm text-surface-500">Inventory location</p>
            </div>
          </div>
          
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-surface-600 dark:text-surface-400">Current</span>
              <span className="font-medium text-surface-900 dark:text-white">
                {currentWarehouse?.name || 'Not set'}
              </span>
            </div>
            
            {canSwitchWarehouse && warehouses.length > 1 && (
              <>
                <div className="divider" />
                <div>
                  <label className="block text-sm text-surface-500 mb-2">Switch Warehouse</label>
                  <select
                    value={currentWarehouse?.id || ''}
                    onChange={(e) => switchWarehouse(Number(e.target.value))}
                    className="select"
                  >
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
            
            <div className="divider" />
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-500">Available Warehouses</span>
              <span className="font-medium text-surface-900 dark:text-white">{warehouses.length}</span>
            </div>
          </div>
        </section>

        {/* User Section */}
        <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '150ms' }}>
          <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-50 dark:bg-purple-500/10 rounded-xl flex items-center justify-center">
              <User className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">Account</h2>
              <p className="text-sm text-surface-500">Profile information</p>
            </div>
          </div>
          
          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between py-2">
              <span className="text-surface-500">Username</span>
              <span className="font-medium text-surface-900 dark:text-white">{user?.username}</span>
            </div>
            <div className="divider" />
            <div className="flex items-center justify-between py-2">
              <span className="text-surface-500">Email</span>
              <span className="text-surface-900 dark:text-white">{user?.email || '—'}</span>
            </div>
            <div className="divider" />
            <div className="flex items-center justify-between py-2">
              <span className="text-surface-500">Role</span>
              <span className={`badge ${user?.role === 'admin' ? 'badge-primary' : 'badge-outline'}`}>
                {user?.role}
              </span>
            </div>
          </div>
        </section>

        {/* Feature Flags Section - Admin Only */}
        {isAdmin && featureFlags && (
          <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '200ms' }}>
            <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-red-50 dark:bg-red-500/10 rounded-xl flex items-center justify-center">
                  <Settings2 className="w-5 h-5 text-red-500" />
                </div>
                <div>
                  <h2 className="font-semibold text-surface-900 dark:text-white">Feature Flags</h2>
                  <p className="text-sm text-surface-500">Enable/disable app features</p>
                </div>
              </div>
              <button
                onClick={resetToDefaults}
                disabled={featureLoading === 'reset'}
                className="text-sm text-surface-500 hover:text-red-500 flex items-center gap-1 transition-colors"
              >
                <RotateCcw className={`w-4 h-4 ${featureLoading === 'reset' ? 'animate-spin' : ''}`} />
                Reset
              </button>
            </div>

            <div className="p-4 space-y-1">
              {featureError && (
                <div className="mb-3 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg text-red-600 dark:text-red-400 text-sm">
                  {featureError}
                </div>
              )}

              {/* Core Features */}
              <p className="text-xs uppercase text-surface-400 font-medium tracking-wide pt-2 pb-1">Core Features</p>
              {(Object.keys(FEATURE_INFO) as (keyof FeatureFlags)[])
                .filter(key => FEATURE_INFO[key].category === 'core')
                .map((featureKey) => (
                  <div
                    key={featureKey}
                    className="flex items-center justify-between py-3 border-b border-surface-100 dark:border-surface-800 last:border-0"
                  >
                    <div>
                      <p className="font-medium text-surface-900 dark:text-white">
                        {FEATURE_INFO[featureKey].name}
                      </p>
                      <p className="text-sm text-surface-500">
                        {FEATURE_INFO[featureKey].description}
                      </p>
                    </div>
                    <button
                      onClick={() => toggleFeature(featureKey)}
                      disabled={featureLoading === featureKey}
                      className={`p-1 rounded-lg transition-colors ${
                        featureFlags[featureKey]
                          ? 'text-green-500 hover:bg-green-50 dark:hover:bg-green-500/10'
                          : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800'
                      }`}
                    >
                      {featureLoading === featureKey ? (
                        <RefreshCw className="w-6 h-6 animate-spin" />
                      ) : featureFlags[featureKey] ? (
                        <ToggleRight className="w-8 h-8" />
                      ) : (
                        <ToggleLeft className="w-8 h-8" />
                      )}
                    </button>
                  </div>
                ))}

              {/* Premium Features */}
              <p className="text-xs uppercase text-surface-400 font-medium tracking-wide pt-4 pb-1">Premium Features</p>
              {(Object.keys(FEATURE_INFO) as (keyof FeatureFlags)[])
                .filter(key => FEATURE_INFO[key].category === 'premium')
                .map((featureKey) => (
                  <div
                    key={featureKey}
                    className="flex items-center justify-between py-3 border-b border-surface-100 dark:border-surface-800 last:border-0"
                  >
                    <div>
                      <p className="font-medium text-surface-900 dark:text-white flex items-center gap-2">
                        {FEATURE_INFO[featureKey].name}
                        <span className="text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 rounded-full">
                          Premium
                        </span>
                      </p>
                      <p className="text-sm text-surface-500">
                        {FEATURE_INFO[featureKey].description}
                      </p>
                    </div>
                    <button
                      onClick={() => toggleFeature(featureKey)}
                      disabled={featureLoading === featureKey}
                      className={`p-1 rounded-lg transition-colors ${
                        featureFlags[featureKey]
                          ? 'text-green-500 hover:bg-green-50 dark:hover:bg-green-500/10'
                          : 'text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800'
                      }`}
                    >
                      {featureLoading === featureKey ? (
                        <RefreshCw className="w-6 h-6 animate-spin" />
                      ) : featureFlags[featureKey] ? (
                        <ToggleRight className="w-8 h-8" />
                      ) : (
                        <ToggleLeft className="w-8 h-8" />
                      )}
                    </button>
                  </div>
                ))}
            </div>
          </section>
        )}

        {/* Install App Section */}
        <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '250ms' }}>
          <div className="p-4 border-b border-surface-200 dark:border-surface-800 flex items-center gap-3">
            <div className="w-10 h-10 bg-green-50 dark:bg-green-500/10 rounded-xl flex items-center justify-center">
              <Download className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">Install App</h2>
              <p className="text-sm text-surface-500">Add to home screen</p>
            </div>
          </div>
          
          <div className="p-4">
            {isInstalled ? (
              <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-500/10 rounded-xl border border-green-200 dark:border-green-500/20">
                <Check className="w-6 h-6 text-green-500" />
                <div>
                  <p className="text-green-600 dark:text-green-400 font-medium">App Installed!</p>
                  <p className="text-sm text-surface-500">You're using the installed version</p>
                </div>
              </div>
            ) : isIOS ? (
              <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-xl">
                <div className="flex items-start gap-4">
                  <Smartphone className="w-8 h-8 text-surface-400 flex-shrink-0 mt-1" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-white mb-2">
                      Install on iPhone / iPad
                    </p>
                    <ol className="text-sm text-surface-500 space-y-1.5 list-decimal list-inside">
                      <li>Tap the <span className="text-primary-500 font-medium">Share</span> button in Safari</li>
                      <li>Scroll down and tap <span className="text-primary-500 font-medium">"Add to Home Screen"</span></li>
                      <li>Tap <span className="text-primary-500 font-medium">Add</span></li>
                    </ol>
                  </div>
                </div>
              </div>
            ) : deferredPrompt ? (
              <button
                onClick={handleInstall}
                className="btn btn-primary w-full py-3"
              >
                <Download className="w-5 h-5" />
                Install TCG Inventory
              </button>
            ) : (
              <div className="p-4 bg-surface-50 dark:bg-surface-800 rounded-xl">
                <div className="flex items-start gap-4">
                  <Monitor className="w-8 h-8 text-surface-400 flex-shrink-0 mt-1" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-white mb-2">
                      Install on Desktop / Android
                    </p>
                    <p className="text-sm text-surface-500">
                      Look for the install icon in your browser's address bar. 
                      For best results, use Chrome or Edge.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
