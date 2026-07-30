import { describe, expect, it } from 'vitest';
import { formatDate, formatDateTime, formatPeriod, getMonthName } from './dates';

describe('formatDate', () => {
  it('μορφοποιεί ISO ημερομηνία σε dd/MM/yyyy', () => {
    expect(formatDate('2026-07-30')).toBe('30/07/2026');
  });

  it('επιστρέφει παύλα για κενά/άκυρα', () => {
    expect(formatDate(null)).toBe('-');
    expect(formatDate(undefined)).toBe('-');
    expect(formatDate('not-a-date')).toBe('-');
  });
});

describe('formatDateTime', () => {
  it('περιλαμβάνει ώρα', () => {
    expect(formatDateTime('2026-07-30T14:35:00')).toBe('30/07/2026 14:35');
  });
});

describe('getMonthName / formatPeriod', () => {
  it('ελληνικά ονόματα μηνών', () => {
    expect(getMonthName(1)).toBe('Ιανουάριος');
    expect(getMonthName(12)).toBe('Δεκέμβριος');
    expect(getMonthName(13)).toBe('');
    expect(getMonthName(0)).toBe('');
  });

  it('formatPeriod συνδυάζει μήνα και έτος', () => {
    expect(formatPeriod(2, 2026)).toBe('Φεβρουάριος 2026');
  });
});
