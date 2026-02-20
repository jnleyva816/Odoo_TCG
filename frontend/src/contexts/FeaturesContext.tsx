// @refresh reset - Context files export both providers and hooks, disable Fast Refresh
import React, { createContext, useContext, useEffect, useState } from 'react';

interface Features {
  sets_page: boolean;
  scanner_page: boolean;
  inventory_page: boolean;
  label_printing: boolean;
  portfolio_dashboard: boolean;
  public_vault: boolean;
}

interface FeaturesContextType {
  features: Features;
  isLoading: boolean;
}

const defaultFeatures: Features = {
  sets_page: false,
  scanner_page: true,
  inventory_page: true,
  label_printing: true,
  portfolio_dashboard: false,
  public_vault: false,
};

const FeaturesContext = createContext<FeaturesContextType>({
  features: defaultFeatures,
  isLoading: true,
});

export function FeaturesProvider({ children }: { children: React.ReactNode }) {
  const [features, setFeatures] = useState<Features>(defaultFeatures);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchFeatures() {
      try {
        const response = await fetch('/api/features');
        if (response.ok) {
          const data = await response.json();
          setFeatures(data);
        }
      } catch (error) {
        console.error('Failed to fetch features:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchFeatures();
  }, []);

  return (
    <FeaturesContext.Provider value={{ features, isLoading }}>
      {children}
    </FeaturesContext.Provider>
  );
}

export function useFeatures() {
  return useContext(FeaturesContext);
}
