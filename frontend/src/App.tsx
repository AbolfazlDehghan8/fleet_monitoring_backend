import { AppProviders } from '@/app/providers';
import { AppRouter } from '@/app/router';
import { AuthProvider } from '@/features/auth/AuthContext';

export default function App() {
  return (
    <AppProviders>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </AppProviders>
  );
}
