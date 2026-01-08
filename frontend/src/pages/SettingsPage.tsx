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
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useFeatures } from '../contexts/FeaturesContext';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export default function SettingsPage() {
  const { user, warehouses, currentWarehouse, switchWarehouse, canSwitchWarehouse } = useAuth();
  const { features } = useFeatures();
  const [printerStatus, setPrinterStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  const printerEnabled = features.label_printing;

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

        {/* Install App Section */}
        <section className="card overflow-hidden animate-slide-in-up" style={{ animationDelay: '200ms' }}>
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
