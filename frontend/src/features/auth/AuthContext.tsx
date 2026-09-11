import * as React from 'react';
import { useNavigate } from 'react-router-dom';

import { authApi } from '@/api/auth';
import { SESSION_EXPIRED_EVENT } from '@/api/client';
import { tokenStorage } from '@/api/tokenStorage';
import type { Role } from '@/constants/roles';
import type { LoginRequest } from '@/types/auth';
import { ApiError } from '@/types/common';

interface SessionUser {
  id: number;
  username: string;
  email: string;
  role: Role;
  first_name: string;
  last_name: string;
}

interface AuthContextValue {
  user: SessionUser | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (payload: LoginRequest) => Promise<SessionUser>;
  logout: () => Promise<void>;
  /** Merges a partial profile update (e.g. after editing the account page) into the
   * session user and persisted storage, so the navbar/sidebar reflect it immediately
   * without a full re-login. */
  updateUser: (patch: Partial<SessionUser>) => void;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

const USER_STORAGE_KEY = 'fleet.auth.user';

function readStoredUser(): SessionUser | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = React.useState<SessionUser | null>(readStoredUser);
  const [isInitializing, setIsInitializing] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const hasToken = Boolean(tokenStorage.getAccessToken());
      if (!hasToken) {
        setIsInitializing(false);
        return;
      }
      try {
        const profile = await authApi.getProfile();
        if (cancelled) return;
        const nextUser: SessionUser = {
          id: profile.id,
          username: profile.username,
          email: profile.email,
          role: profile.role,
          first_name: profile.first_name,
          last_name: profile.last_name,
        };
        setUser(nextUser);
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          tokenStorage.clear();
          localStorage.removeItem(USER_STORAGE_KEY);
          setUser(null);
        }
      } finally {
        if (!cancelled) setIsInitializing(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    function handleSessionExpired() {
      setUser(null);
      localStorage.removeItem(USER_STORAGE_KEY);
      navigate('/login', { replace: true });
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
  }, [navigate]);

  const login = React.useCallback(async (payload: LoginRequest) => {
    const response = await authApi.login(payload);
    tokenStorage.setTokens(response.access_token, response.refresh_token);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user));
    setUser(response.user);
    return response.user;
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await authApi.logout(tokenStorage.getRefreshToken() ?? undefined);
    } catch {
      // Best-effort: proceed with local logout regardless of API result.
    }
    tokenStorage.clear();
    localStorage.removeItem(USER_STORAGE_KEY);
    setUser(null);
    navigate('/login', { replace: true });
  }, [navigate]);

  const updateUser = React.useCallback((patch: Partial<SessionUser>) => {
    setUser((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...patch };
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const value = React.useMemo(
    () => ({ user, isAuthenticated: Boolean(user), isInitializing, login, logout, updateUser }),
    [user, isInitializing, login, logout, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
