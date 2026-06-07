import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';

// Types for calendar data
export interface CalendarObligation {
  id: number;
  client_name: string;
  client_id: number;
  type_name: string;
  type_code: string;
  status: 'pending' | 'completed' | 'overdue' | 'in_progress' | 'cancelled';
  deadline: string;
  notes: string;
}

export interface CalendarDay {
  total: number;
  pending: number;
  completed: number;
  overdue: number;
  in_progress: number;
  cancelled: number;
  obligations: CalendarObligation[];
}

export interface CalendarSummary {
  total: number;
  pending: number;
  completed: number;
  overdue: number;
  in_progress: number;
  cancelled: number;
}

export interface CalendarData {
  month: number;
  year: number;
  days: Record<string, CalendarDay>;
  summary: CalendarSummary;
}

// Filter parameters for the calendar
export interface CalendarFilters {
  client_id?: number;
  type_id?: number;
  status?: string;
}

const CALENDAR_KEY = 'calendar';

/**
 * Hook to fetch calendar data for a specific month/year
 *
 * @param month - Month number (1-12)
 * @param year - Year (e.g., 2025)
 * @param filters - Optional filters for client, type, status
 */
export function useCalendar(month: number, year: number, filters?: CalendarFilters) {
  return useQuery({
    queryKey: [CALENDAR_KEY, month, year, filters],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        month,
        year,
      };

      if (filters?.client_id) {
        params.client_id = filters.client_id;
      }
      if (filters?.type_id) {
        params.type_id = filters.type_id;
      }
      if (filters?.status) {
        params.status = filters.status;
      }

      const response = await apiClient.get<CalendarData>('/api/v1/obligations/calendar/', {
        params,
      });
      return response.data;
    },
    staleTime: 1000 * 60 * 2, // Cache for 2 minutes
  });
}

// Greek month names
export const GREEK_MONTH_NAMES = [
  'Ιανουάριος',
  'Φεβρουάριος',
  'Μάρτιος',
  'Απρίλιος',
  'Μάιος',
  'Ιούνιος',
  'Ιούλιος',
  'Αύγουστος',
  'Σεπτέμβριος',
  'Οκτώβριος',
  'Νοέμβριος',
  'Δεκέμβριος',
];

// Greek day names (short)
export const GREEK_DAY_NAMES = ['Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ', 'Κυρ'];

// Greek day names (full)
export const GREEK_DAY_NAMES_FULL = [
  'Δευτέρα',
  'Τρίτη',
  'Τετάρτη',
  'Πέμπτη',
  'Παρασκευή',
  'Σάββατο',
  'Κυριακή',
];

/**
 * Get the number of days in a month
 */
export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/**
 * Get the first day of the week for a month (0 = Monday, 6 = Sunday)
 * JavaScript getDay() returns 0 for Sunday, we adjust for Monday-first week
 */
export function getFirstDayOfMonth(year: number, month: number): number {
  const day = new Date(year, month - 1, 1).getDay();
  // Convert from Sunday=0 to Monday=0
  return day === 0 ? 6 : day - 1;
}

/**
 * Check if a date is today
 */
export function isToday(year: number, month: number, day: number): boolean {
  const today = new Date();
  return (
    today.getFullYear() === year &&
    today.getMonth() + 1 === month &&
    today.getDate() === day
  );
}

/**
 * Get status color class for an obligation status
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'text-green-600 bg-green-100';
    case 'pending':
      return 'text-yellow-600 bg-yellow-100';
    case 'overdue':
      return 'text-red-600 bg-red-100';
    case 'in_progress':
      return 'text-brand-600 bg-brand-100';
    case 'cancelled':
      return 'text-gray-600 bg-gray-100';
    default:
      return 'text-gray-600 bg-gray-100';
  }
}

/**
 * Get Greek label for status
 */
export function getStatusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return 'Ολοκληρωμένη';
    case 'pending':
      return 'Εκκρεμεί';
    case 'overdue':
      return 'Εκπρόθεσμη';
    case 'in_progress':
      return 'Σε εξέλιξη';
    case 'cancelled':
      return 'Ακυρωμένη';
    default:
      return status;
  }
}

/**
 * Hook to update obligation status
 */
export function useUpdateObligationStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) => {
      const response = await apiClient.patch(`/api/v1/obligations/${id}/`, {
        status,
        ...(status === 'completed' ? { completed_date: new Date().toISOString().split('T')[0] } : {}),
      });
      return response.data;
    },
    onSuccess: () => {
      // Invalidate calendar queries to refresh the data
      queryClient.invalidateQueries({ queryKey: [CALENDAR_KEY] });
    },
  });
}

/**
 * Hook to mark obligation as completed
 */
export function useCompleteObligation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.patch(`/api/v1/obligations/${id}/complete/`);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all calendar and obligations queries
      queryClient.invalidateQueries({ queryKey: [CALENDAR_KEY] });
      queryClient.invalidateQueries({ queryKey: ['obligations'] });
    },
  });
}
