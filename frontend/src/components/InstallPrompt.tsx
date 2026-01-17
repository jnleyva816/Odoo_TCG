import { useState, useEffect } from 'react';
import { Download, X } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    // Check if already installed
    if (window.matchMedia('(display-mode: standalone)').matches) {
      return; // Already installed as PWA
    }

    // Check if iOS
    const isIOSDevice = /iPad|iPhone|iPod/.test(navigator.userAgent);
    setIsIOS(isIOSDevice);

    // Listen for install prompt (Android/Desktop)
    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setShowPrompt(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);

    // Show iOS prompt after a delay if not dismissed before
    if (isIOSDevice && !localStorage.getItem('pwa-install-dismissed')) {
      setTimeout(() => setShowPrompt(true), 3000);
    }

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;

    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      console.log('✅ PWA installed');
    }
    
    setDeferredPrompt(null);
    setShowPrompt(false);
  };

  const handleDismiss = () => {
    setShowPrompt(false);
    localStorage.setItem('pwa-install-dismissed', 'true');
  };

  if (!showPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 animate-slide-up">
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-2xl p-4 flex items-center gap-4">
        <div className="flex-shrink-0 bg-white/20 rounded-lg p-2">
          <Download className="w-6 h-6 text-white" />
        </div>
        
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold text-sm">Install TCG Inventory</h3>
          {isIOS ? (
            <p className="text-blue-100 text-xs mt-0.5">
              Tap <span className="inline-block px-1 bg-white/20 rounded">Share</span> then "Add to Home Screen"
            </p>
          ) : (
            <p className="text-blue-100 text-xs mt-0.5">
              Add to your home screen for quick access
            </p>
          )}
        </div>

        {!isIOS && (
          <button
            onClick={handleInstall}
            className="flex-shrink-0 bg-white text-blue-600 px-4 py-2 rounded-lg font-semibold text-sm hover:bg-blue-50 transition-colors"
          >
            Install
          </button>
        )}

        <button
          onClick={handleDismiss}
          className="flex-shrink-0 text-white/70 hover:text-white p-1"
          aria-label="Dismiss"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}


