/**
 * Consolidated constants for the LogistikoCRM frontend
 * All shared constants should be imported from this file
 */

// ============================================
// TYPE DEFINITIONS
// ============================================

export type ObligationStatus = 'pending' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';
export type TicketStatus = 'open' | 'assigned' | 'in_progress' | 'resolved' | 'closed';
export type Priority = 'low' | 'medium' | 'high' | 'urgent';
export type CallStatus = 'active' | 'completed' | 'missed' | 'failed';

// ============================================
// OBLIGATION STATUS CONSTANTS
// ============================================

/** Status labels for obligations - singular form (used in tables and badges) */
export const OBLIGATION_STATUS_LABELS: Record<string, string> = {
  pending: 'Εκκρεμεί',
  in_progress: 'Σε εξέλιξη',
  completed: 'Ολοκληρώθηκε',
  overdue: 'Εκπρόθεσμη',
  cancelled: 'Ακυρώθηκε',
};

/** Status labels for obligations - plural form (used in Dashboard charts) */
export const OBLIGATION_STATUS_LABELS_PLURAL: Record<string, string> = {
  pending: 'Εκκρεμείς',
  in_progress: 'Σε εξέλιξη',
  completed: 'Ολοκληρωμένες',
  overdue: 'Εκπρόθεσμες',
  cancelled: 'Ακυρωμένες',
};

/** Status colors for obligation badges - Tailwind classes */
export const OBLIGATION_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-brand-100 text-brand-800',
  completed: 'bg-green-100 text-green-800',
  overdue: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

/** Status colors for obligations - Hex colors (for charts) */
export const OBLIGATION_STATUS_COLORS_HEX: Record<string, string> = {
  pending: '#EAB308',      // yellow-500
  in_progress: '#3B82F6',  // blue-500
  completed: '#22C55E',    // green-500
  overdue: '#EF4444',      // red-500
  cancelled: '#6B7280',    // gray-500
};

// ============================================
// TICKET STATUS CONSTANTS
// ============================================

/** Status labels for tickets */
export const TICKET_STATUS_LABELS: Record<string, string> = {
  open: 'Ανοιχτό',
  assigned: 'Ανατέθηκε',
  in_progress: 'Σε εξέλιξη',
  resolved: 'Επιλύθηκε',
  closed: 'Κλειστό',
};

/** Status colors for ticket badges - Tailwind classes */
export const TICKET_STATUS_COLORS: Record<string, string> = {
  open: 'bg-brand-100 text-brand-800',
  assigned: 'bg-cyan-100 text-cyan-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-800',
};

/** Ticket status options for filter dropdowns */
export const TICKET_STATUS_OPTIONS = [
  { value: '', label: 'Όλες' },
  { value: 'open', label: 'Ανοιχτά' },
  { value: 'in_progress', label: 'Σε εξέλιξη' },
  { value: 'resolved', label: 'Επιλύθηκε' },
  { value: 'closed', label: 'Κλειστά' },
] as const;

// ============================================
// PRIORITY CONSTANTS
// ============================================

/** Priority labels in Greek */
export const PRIORITY_LABELS: Record<string, string> = {
  low: 'Χαμηλή',
  medium: 'Μεσαία',
  high: 'Υψηλή',
  urgent: 'Επείγον',
};

/** Priority colors - Tailwind classes */
export const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  urgent: 'bg-red-100 text-red-800',
};

/** Priority options for filter dropdowns */
export const PRIORITY_OPTIONS = [
  { value: '', label: 'Όλες' },
  { value: 'urgent', label: 'Επείγον' },
  { value: 'high', label: 'Υψηλή' },
  { value: 'medium', label: 'Μεσαία' },
  { value: 'low', label: 'Χαμηλή' },
] as const;

// ============================================
// CALL STATUS CONSTANTS
// ============================================

/** Call status colors - text color classes (different format for call icons) */
export const CALL_STATUS_COLORS: Record<string, string> = {
  active: 'text-brand-600',
  completed: 'text-green-600',
  missed: 'text-red-600',
  failed: 'text-gray-600',
};

/** Call status colors - badge format with background (for SearchModal) */
export const CALL_STATUS_BADGE_COLORS: Record<string, string> = {
  active: 'bg-brand-100 text-brand-700',
  completed: 'bg-green-100 text-green-700',
  missed: 'bg-red-100 text-red-700',
  failed: 'bg-gray-100 text-gray-700',
};

/** Call direction options for filter dropdowns */
export const CALL_DIRECTION_OPTIONS = [
  { value: '', label: 'Όλες' },
  { value: 'incoming', label: 'Εισερχόμενες' },
  { value: 'outgoing', label: 'Εξερχόμενες' },
  { value: 'missed', label: 'Αναπάντητες' },
] as const;

// ============================================
// DATE / TIME CONSTANTS
// ============================================

/** Greek month names - array format (0-indexed, for date formatting) */
export const MONTH_NAMES = [
  'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος',
  'Μάιος', 'Ιούνιος', 'Ιούλιος', 'Αύγουστος',
  'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος',
] as const;

/** Greek months - object format for select dropdowns (1-indexed) */
export const MONTHS = [
  { value: 1, label: 'Ιανουάριος' },
  { value: 2, label: 'Φεβρουάριος' },
  { value: 3, label: 'Μάρτιος' },
  { value: 4, label: 'Απρίλιος' },
  { value: 5, label: 'Μάιος' },
  { value: 6, label: 'Ιούνιος' },
  { value: 7, label: 'Ιούλιος' },
  { value: 8, label: 'Αύγουστος' },
  { value: 9, label: 'Σεπτέμβριος' },
  { value: 10, label: 'Οκτώβριος' },
  { value: 11, label: 'Νοέμβριος' },
  { value: 12, label: 'Δεκέμβριος' },
] as const;

/** Greek quarter names */
export const QUARTERS = ['1ο Τρίμηνο', '2ο Τρίμηνο', '3ο Τρίμηνο', '4ο Τρίμηνο'] as const;

/** Greek short day names (Mon-Sun) */
export const GREEK_DAY_NAMES = ['Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ', 'Κυρ'] as const;

/** Generate years array centered around current year */
export const getYearsArray = (range: number = 2): number[] => {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: range * 2 + 1 }, (_, i) => currentYear - range + i);
};

/** Default years array (current year ± 2) */
export const YEARS = getYearsArray(2);

// ============================================
// OBLIGATION STATUS OPTIONS (for forms)
// ============================================

/** Obligation status options for select dropdowns */
export const OBLIGATION_STATUS_OPTIONS: { value: ObligationStatus; label: string }[] = [
  { value: 'pending', label: 'Εκκρεμεί' },
  { value: 'in_progress', label: 'Σε εξέλιξη' },
  { value: 'completed', label: 'Ολοκληρώθηκε' },
  { value: 'overdue', label: 'Εκπρόθεσμη' },
  { value: 'cancelled', label: 'Ακυρώθηκε' },
];
