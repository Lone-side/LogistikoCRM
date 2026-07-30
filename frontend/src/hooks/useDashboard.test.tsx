import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { useDashboardStats } from './useDashboard';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('../api/client', () => ({
  default: { get: mockGet },
  apiClient: { get: mockGet },
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const STATS = {
  total_clients: 12,
  total_obligations_pending: 5,
  total_obligations_completed_this_month: 3,
  overdue_count: 1,
  upcoming_deadlines: [],
  upcoming_count: 0,
  status_breakdown: {},
  top_obligation_types: [],
  type_breakdown: [],
  team_workload: [
    { user_id: 1, name: 'Μαρία Π.', open: 4, overdue: 1, completed_this_month: 3 },
  ],
  monthly_trend: [
    { year: 2026, month: 7, label: 'Ιούλ 26', total: 8, completed: 3 },
  ],
  current_period: { month: 7, year: 2026 },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useDashboardStats', () => {
  it('φέρνει τα στατιστικά από το σωστό endpoint', async () => {
    mockGet.mockResolvedValue({ data: STATS });

    const { result } = renderHook(() => useDashboardStats(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith('/api/dashboard/stats/');
    expect(result.current.data?.total_clients).toBe(12);
    expect(result.current.data?.team_workload[0].name).toBe('Μαρία Π.');
  });

  it('εκθέτει σφάλμα όταν το αίτημα αποτύχει', async () => {
    mockGet.mockRejectedValue(new Error('network'));

    const { result } = renderHook(() => useDashboardStats(), { wrapper });

    // Το hook κάνει retry: 1 εσωτερικά — περιμένουμε και το retry
    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 8000,
    });
  }, 10000);
});
