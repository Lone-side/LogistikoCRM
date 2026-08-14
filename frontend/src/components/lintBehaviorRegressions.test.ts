import { describe, expect, it } from 'vitest';
import type { Obligation } from '../types';
import {
  hasActiveTicketFilters,
  initialObligationFormData,
  periodForType,
} from '../utils/lintBehavior';

describe('lint cleanup behavior regressions', () => {
  it('initializes an edit form from the existing obligation', () => {
    const obligation: Obligation = {
      id: 42,
      client: 7,
      obligation_type: 3,
      month: 11,
      year: 2026,
      deadline: '2026-12-20',
      status: 'completed',
      completed_date: '2026-12-18',
      time_spent: 90,
      notes: 'Υφιστάμενη σημείωση',
      assigned_to: 5,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
    };

    expect(initialObligationFormData(obligation)).toMatchObject({
      client: 7,
      obligation_type: 3,
      month: 11,
      year: 2026,
      deadline: '2026-12-20',
      status: 'completed',
      completed_date: '2026-12-18',
      time_spent: 90,
      notes: 'Υφιστάμενη σημείωση',
      assigned_to: 5,
    });
  });

  it.each([
    [4, 2],
    [8, 3],
    [12, 4],
  ])('converts month %i to quarter %i exactly once', (month, quarter) => {
    expect(periodForType(month, 'quarterly')).toBe(quarter);
  });

  it('treats search text as an active ticket filter', () => {
    expect(hasActiveTicketFilters({ page: 1, page_size: 20 }, 'πελάτης')).toBe(true);
    expect(hasActiveTicketFilters({ page: 1, page_size: 20 }, '')).toBe(false);
  });
});
