import type { Obligation, ObligationFormData } from '../types';
import type { TicketsFilters } from '../hooks/useTickets';

export function initialObligationFormData(
  obligation?: Obligation | null,
  currentDate = new Date()
): ObligationFormData {
  if (obligation) {
    return {
      client: obligation.client,
      obligation_type: obligation.obligation_type,
      month: obligation.month,
      year: obligation.year,
      deadline: obligation.deadline,
      status: obligation.status,
      completed_date: obligation.completed_date || null,
      time_spent: obligation.time_spent || null,
      notes: obligation.notes || '',
      assigned_to: obligation.assigned_to || null,
    };
  }

  return {
    client: 0,
    obligation_type: 0,
    month: currentDate.getMonth() + 1,
    year: currentDate.getFullYear(),
    deadline: '',
    status: 'pending',
    completed_date: null,
    time_spent: null,
    notes: '',
    assigned_to: null,
  };
}

export function periodForType(
  current: number,
  periodType: 'monthly' | 'quarterly'
): number {
  return periodType === 'quarterly'
    ? Math.ceil(current / 3)
    : Math.min(current, 12);
}

export function hasActiveTicketFilters(
  filters: TicketsFilters,
  searchInput: string
): boolean {
  return Boolean(
    filters.status
    || filters.priority
    || searchInput
    || filters.open_only
    || filters.client_id
  );
}
