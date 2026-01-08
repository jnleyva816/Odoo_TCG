// @refresh reset - Context files export both providers and hooks, disable Fast Refresh
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getWarehouses, switchWarehouse as apiSwitchWarehouse, Warehouse, onAuthFailure } from '../api/client';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
  warehouse_id: number | null;
  warehouse_ids: number[] | null;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  // Warehouse support
  warehouses: Warehouse[];
  currentWarehouse: Warehouse | null;
  canSwitchWarehouse: boolean;
  switchWarehouse: (warehouseId: number) => Promise<void>;
  refreshWarehouses: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'tcg_auth_token';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem(TOKEN_KEY);
  });
  const [isLoading, setIsLoading] = useState(true);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);

  // Compute current warehouse from user and warehouses list
  const currentWarehouse = user?.warehouse_id
    ? warehouses.find((w) => w.id === user.warehouse_id) || null
    : warehouses[0] || null;

  // Admin users with multiple warehouses can switch
  const canSwitchWarehouse = user?.role === 'admin' && warehouses.length > 1;

  // Fetch warehouses
  const refreshWarehouses = useCallback(async () => {
    try {
      const warehouseList = await getWarehouses();
      setWarehouses(warehouseList);
    } catch (error) {
      console.error('Failed to fetch warehouses:', error);
      setWarehouses([]);
    }
  }, []);

  // Verify token on mount
  useEffect(() => {
    async function verifyToken() {
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch('/api/auth/me', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else {
          // Token invalid, clear it
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      } catch (error) {
        console.error('Token verification failed:', error);
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    }

    verifyToken();
  }, [token]);

  // Fetch warehouses when user is set
  useEffect(() => {
    if (user) {
      refreshWarehouses();
    } else {
      setWarehouses([]);
    }
  }, [user, refreshWarehouses]);

  // Listen for auth failures from API calls
  useEffect(() => {
    return onAuthFailure(() => {
      // Only logout if we're not already loading (avoids race during HMR)
      if (!isLoading) {
        setUser(null);
        setToken(null);
        setWarehouses([]);
      }
    });
  }, [isLoading]);

  const login = async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    const newToken = data.token.access_token;
    
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setWarehouses([]);
  };

  const switchWarehouse = async (warehouseId: number) => {
    if (!user || user.role !== 'admin') {
      throw new Error('Only admins can switch warehouses');
    }

    const result = await apiSwitchWarehouse(warehouseId);
    
    // Store the new token (contains updated warehouse)
    if (result.new_token) {
      localStorage.setItem(TOKEN_KEY, result.new_token);
      setToken(result.new_token);
    }
    
    // Update local user state
    setUser({ ...user, warehouse_id: warehouseId });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        warehouses,
        currentWarehouse,
        canSwitchWarehouse,
        switchWarehouse,
        refreshWarehouses,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

