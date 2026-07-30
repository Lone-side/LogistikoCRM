import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';

interface UpcomingDeadline {
  id: number;
  client_name: string;
  client_afm: string;
  type: string;
  type_code: string;
  deadline: string;
  days_until: number;
}

interface DashboardStats {
  total_clients: number;
  total_obligations_pending: number;
  total_obligations_completed_this_month: number;
  overdue_count: number;
  upcoming_deadlines: UpcomingDeadline[];
  upcoming_count: number;
  status_breakdown: Record<string, number>;
  top_obligation_types: Array<{ obligation_type__name: string; count: number }>;
  type_breakdown: Array<{
    obligation_type__name: string;
    obligation_type__code: string;
    total: number;
    completed: number;
    pending: number;
    overdue: number;
  }>;
  team_workload: Array<{
    user_id: number | null;
    name: string;
    open: number;
    overdue: number;
    completed_this_month: number;
  }>;
  monthly_trend: Array<{
    year: number;
    month: number;
    label: string;
    total: number;
    completed: number;
  }>;
  current_period: {
    month: number;
    year: number;
  };
}

const DASHBOARD_KEY = 'dashboard';

export function useDashboardStats() {
  return useQuery({
    queryKey: [DASHBOARD_KEY, 'stats'],
    queryFn: async () => {
      const response = await apiClient.get<DashboardStats>('/api/dashboard/stats/');
      return response.data;
    },
    staleTime: 30000, // 30 seconds
    retry: 1,
  });
}

interface CalendarEvent {
  date: string;
  count: number;
  obligations: Array<{
    id: number;
    client_name: string;
    client_afm: string;
    type: string;
    type_code: string;
    status: string;
  }>;
}

interface CalendarData {
  month: number;
  year: number;
  first_day: string;
  last_day: string;
  total_obligations: number;
  pending: number;
  completed: number;
  overdue: number;
  events: CalendarEvent[];
}

export function useDashboardCalendar(month?: number, year?: number) {
  return useQuery({
    queryKey: [DASHBOARD_KEY, 'calendar', month, year],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (month) params.append('month', month.toString());
      if (year) params.append('year', year.toString());

      const url = params.toString()
        ? `/api/dashboard/calendar/?${params.toString()}`
        : '/api/dashboard/calendar/';

      const response = await apiClient.get<CalendarData>(url);
      return response.data;
    },
    staleTime: 60000, // 1 minute
  });
}

interface RecentActivity {
  recent_completions: Array<{
    id: number;
    type: string;
    client_name: string;
    obligation_type: string;
    completed_date: string | null;
    completed_by: string | null;
    period: string;
  }>;
  new_clients: Array<{
    id: number;
    type: string;
    eponimia: string;
    afm: string;
    created_at: string;
  }>;
}

export function useDashboardRecentActivity(limit = 10) {
  return useQuery({
    queryKey: [DASHBOARD_KEY, 'recent-activity', limit],
    queryFn: async () => {
      const response = await apiClient.get<RecentActivity>(`/api/dashboard/recent-activity/?limit=${limit}`);
      return response.data;
    },
    staleTime: 30000,
  });
}
