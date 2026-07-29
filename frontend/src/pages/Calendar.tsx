import { useState, useMemo, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  X,
  Filter,
  ExternalLink,
  Check,
  Edit3,
  Clock,
  AlertCircle,
  FileText,
  Calendar as CalendarIcon,
  Zap,
  CheckCircle,
} from 'lucide-react';
import {
  useCalendar,
  useCompleteObligation,
  GREEK_MONTH_NAMES,
  GREEK_DAY_NAMES,
  getDaysInMonth,
  getFirstDayOfMonth,
  isToday,
  getStatusColor,
  getStatusLabel,
} from '../hooks/useCalendar';
import type {
  CalendarDay as CalendarDayType,
  CalendarObligation,
} from '../hooks/useCalendar';
import { useClients } from '../hooks/useClients';
import { useObligationTypes } from '../hooks/useObligations';
import { useToast } from '../components/Toast';
import { CompleteObligationModal } from '../components/CompleteObligationModal';
import { useCompleteAndNotify } from '../hooks/useEmail';
import type { Obligation } from '../types';

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

interface CalendarDayProps {
  day: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  dayData?: CalendarDayType;
  onClick: () => void;
}

function CalendarDayCell({ day, isCurrentMonth, isToday: isTodayDay, dayData, onClick }: CalendarDayProps) {
  const hasObligations = dayData && dayData.total > 0;

  return (
    <button
      onClick={onClick}
      disabled={!isCurrentMonth}
      className={`
        min-h-[80px] md:min-h-[100px] p-1 md:p-2 border border-gray-200 text-left transition-colors
        ${isCurrentMonth ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 text-gray-400'}
        ${isTodayDay ? 'ring-2 ring-blue-500 ring-inset' : ''}
        ${hasObligations ? 'cursor-pointer' : 'cursor-default'}
      `}
    >
      <div className="flex flex-col h-full">
        {/* Day number */}
        <span
          className={`
            text-sm md:text-base font-medium
            ${isTodayDay ? 'text-blue-600 font-bold' : ''}
          `}
        >
          {day}
        </span>

        {/* Obligations summary */}
        {hasObligations && dayData && (
          <div className="mt-1 space-y-0.5 flex-1 overflow-hidden">
            {/* Status indicators */}
            <div className="flex flex-wrap gap-1">
              {dayData.pending > 0 && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                  {dayData.pending}
                </span>
              )}
              {dayData.completed > 0 && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                  {dayData.completed}
                </span>
              )}
              {dayData.overdue > 0 && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                  {dayData.overdue}
                </span>
              )}
            </div>

            {/* Show first 2 obligations on larger screens */}
            <div className="hidden md:block space-y-0.5">
              {dayData.obligations.slice(0, 2).map((obl) => (
                <div
                  key={obl.id}
                  className={`text-xs truncate px-1 py-0.5 rounded ${getStatusColor(obl.status)}`}
                  title={`${obl.client_name} - ${obl.type_name}`}
                >
                  {obl.type_code}
                </div>
              ))}
              {dayData.obligations.length > 2 && (
                <div className="text-xs text-gray-500">
                  +{dayData.obligations.length - 2} ακόμη
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </button>
  );
}

interface DayDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  day: number;
  month: number;
  year: number;
  dayData?: CalendarDayType;
  onQuickComplete: (id: number) => void;
  onFullComplete: (obligation: CalendarObligation) => void;
  isCompleting: boolean;
}

function DayDetailModal({
  isOpen,
  onClose,
  day,
  month,
  year,
  dayData,
  onQuickComplete,
  onFullComplete,
  isCompleting,
}: DayDetailModalProps) {
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const dateStr = `${day} ${GREEK_MONTH_NAMES[month - 1]} ${year}`;
  const today = new Date();
  const isDateToday = today.getFullYear() === year && today.getMonth() + 1 === month && today.getDate() === day;
  const isPastDate = new Date(year, month - 1, day) < new Date(today.getFullYear(), today.getMonth(), today.getDate());

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden">
          {/* Header */}
          <div className={`flex items-center justify-between p-4 border-b border-gray-200 ${
            isDateToday ? 'bg-blue-50' : isPastDate ? 'bg-gray-50' : 'bg-white'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${
                isDateToday ? 'bg-blue-100' : 'bg-gray-100'
              }`}>
                <CalendarIcon size={20} className={isDateToday ? 'text-blue-600' : 'text-gray-600'} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{dateStr}</h3>
                {isDateToday && (
                  <span className="text-xs text-blue-600 font-medium">Σήμερα</span>
                )}
                {isPastDate && !isDateToday && (
                  <span className="text-xs text-gray-500">Παρελθούσα ημερομηνία</span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Κλείσιμο"
            >
              <X size={20} className="text-gray-500" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4 overflow-y-auto max-h-[65vh]">
            {dayData && dayData.obligations.length > 0 ? (
              <>
                {/* Summary badges */}
                <div className="flex flex-wrap gap-2 mb-4 pb-4 border-b border-gray-200">
                  <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-700">
                    Σύνολο: {dayData.total}
                  </span>
                  {dayData.pending > 0 && (
                    <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 flex items-center gap-1">
                      <Clock size={14} />
                      Εκκρεμείς: {dayData.pending}
                    </span>
                  )}
                  {dayData.in_progress > 0 && (
                    <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-blue-100 text-blue-800 flex items-center gap-1">
                      <Clock size={14} />
                      Σε εξέλιξη: {dayData.in_progress}
                    </span>
                  )}
                  {dayData.completed > 0 && (
                    <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-800 flex items-center gap-1">
                      <Check size={14} />
                      Ολοκληρωμένες: {dayData.completed}
                    </span>
                  )}
                  {dayData.overdue > 0 && (
                    <span className="px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-800 flex items-center gap-1">
                      <AlertCircle size={14} />
                      Εκπρόθεσμες: {dayData.overdue}
                    </span>
                  )}
                </div>

                {/* Obligations list */}
                <div className="space-y-3">
                  {dayData.obligations.map((obl: CalendarObligation) => (
                    <div
                      key={obl.id}
                      className={`p-4 rounded-lg border transition-all ${
                        obl.status === 'completed'
                          ? 'bg-green-50 border-green-200'
                          : obl.status === 'overdue'
                          ? 'bg-red-50 border-red-200'
                          : obl.status === 'in_progress'
                          ? 'bg-blue-50 border-blue-200'
                          : 'bg-white border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          {/* Type badge and status */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`px-2.5 py-1 rounded-md text-xs font-bold ${getStatusColor(obl.status)}`}
                            >
                              {obl.type_code}
                            </span>
                            <span className={`text-xs font-medium ${
                              obl.status === 'overdue' ? 'text-red-600' :
                              obl.status === 'completed' ? 'text-green-600' :
                              obl.status === 'in_progress' ? 'text-blue-600' :
                              'text-gray-500'
                            }`}>
                              {getStatusLabel(obl.status)}
                            </span>
                          </div>

                          {/* Client name */}
                          <p className="mt-2 text-base font-semibold text-gray-900">
                            {obl.client_name}
                          </p>

                          {/* Type name */}
                          <p className="text-sm text-gray-600">{obl.type_name}</p>

                          {/* Notes if present */}
                          {obl.notes && (
                            <div className="mt-2 flex items-start gap-1.5 text-xs text-gray-500">
                              <FileText size={12} className="mt-0.5 flex-shrink-0" />
                              <span className="line-clamp-2">{obl.notes}</span>
                            </div>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex flex-col gap-1.5">
                          {/* Complete buttons - only for non-completed obligations */}
                          {obl.status !== 'completed' && obl.status !== 'cancelled' && (
                            <>
                              {/* Quick complete */}
                              <button
                                onClick={() => onQuickComplete(obl.id)}
                                disabled={isCompleting}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title="Γρήγορη ολοκλήρωση"
                              >
                                <Zap size={14} />
                                <span className="hidden sm:inline">Γρήγορη</span>
                              </button>
                              {/* Full complete with modal */}
                              <button
                                onClick={() => onFullComplete(obl)}
                                disabled={isCompleting}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-100 hover:bg-emerald-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                title="Ολοκλήρωση με έγγραφα & email"
                              >
                                <CheckCircle size={14} />
                                <span className="hidden sm:inline">Πλήρης</span>
                              </button>
                            </>
                          )}

                          {/* Edit link */}
                          <Link
                            to={`/obligations/${obl.id}/edit`}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                            title="Επεξεργασία"
                          >
                            <Edit3 size={14} />
                            <span className="hidden sm:inline">Επεξεργασία</span>
                          </Link>

                          {/* View client */}
                          <Link
                            to={`/clients/${obl.client_id}`}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-100 hover:bg-blue-200 rounded-lg transition-colors"
                            title="Προβολή πελάτη"
                          >
                            <ExternalLink size={14} />
                            <span className="hidden sm:inline">Πελάτης</span>
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <CalendarIcon size={48} className="mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500 font-medium">
                  Δεν υπάρχουν υποχρεώσεις για αυτή την ημερομηνία.
                </p>
              </div>
            )}
          </div>

          {/* Footer with keyboard hint */}
          <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-center">
            <span className="text-xs text-gray-400">
              Πατήστε <kbd className="px-1.5 py-0.5 bg-gray-200 rounded text-gray-600">Esc</kbd> για κλείσιμο
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface CalendarGridProps {
  month: number;
  year: number;
  days: Record<string, CalendarDayType>;
  onDayClick: (day: number) => void;
}

function CalendarGrid({ month, year, days, onDayClick }: CalendarGridProps) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDayOfWeek = getFirstDayOfMonth(year, month);

  // Calculate previous month's trailing days
  const prevMonth = month === 1 ? 12 : month - 1;
  const prevYear = month === 1 ? year - 1 : year;
  const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth);

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const result: Array<{ day: number; isCurrentMonth: boolean }> = [];

    // Previous month's trailing days
    for (let i = firstDayOfWeek - 1; i >= 0; i--) {
      result.push({ day: daysInPrevMonth - i, isCurrentMonth: false });
    }

    // Current month's days
    for (let day = 1; day <= daysInMonth; day++) {
      result.push({ day, isCurrentMonth: true });
    }

    // Next month's leading days (fill to complete the grid)
    const remainingDays = 42 - result.length; // 6 rows × 7 days
    for (let day = 1; day <= remainingDays; day++) {
      result.push({ day, isCurrentMonth: false });
    }

    return result;
  }, [month, year, daysInMonth, firstDayOfWeek, daysInPrevMonth]);

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Day headers */}
      <div className="grid grid-cols-7 bg-gray-100 border-b border-gray-200">
        {GREEK_DAY_NAMES.map((dayName) => (
          <div
            key={dayName}
            className="py-2 text-center text-xs md:text-sm font-medium text-gray-600"
          >
            {dayName}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {calendarDays.map((item, index) => (
          <CalendarDayCell
            key={index}
            day={item.day}
            isCurrentMonth={item.isCurrentMonth}
            isToday={item.isCurrentMonth && isToday(year, month, item.day)}
            dayData={item.isCurrentMonth ? days[String(item.day)] : undefined}
            onClick={() => item.isCurrentMonth && onDayClick(item.day)}
          />
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// MAIN CALENDAR PAGE
// =============================================================================

export default function Calendar() {
  const today = new Date();
  const [currentMonth, setCurrentMonth] = useState(today.getMonth() + 1);
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Complete modal state
  const [isCompleteModalOpen, setIsCompleteModalOpen] = useState(false);
  const [selectedObligation, setSelectedObligation] = useState<CalendarObligation | null>(null);

  // Filter state
  const [filters, setFilters] = useState<{
    client_id?: number;
    type_id?: number;
    status?: string;
  }>({});

  // Toast notifications
  const { showToast } = useToast();

  // Fetch calendar data
  const {
    data: calendarData,
    isLoading,
    isError,
    error,
  } = useCalendar(currentMonth, currentYear, filters);

  // Fetch clients and obligation types for filters
  const { data: clientsData } = useClients({ page_size: 1000 });
  const { data: obligationTypes } = useObligationTypes();

  // Mutations
  const quickCompleteMutation = useCompleteObligation();
  const completeAndNotifyMutation = useCompleteAndNotify();

  // Handle quick complete (no modal)
  const handleQuickComplete = useCallback((obligationId: number) => {
    quickCompleteMutation.mutate(obligationId, {
      onSuccess: () => {
        showToast('success', 'Ολοκληρώθηκε!', 'Η υποχρέωση ολοκληρώθηκε επιτυχώς');
      },
      onError: (err) => {
        showToast('error', 'Σφάλμα', err instanceof Error ? err.message : 'Αποτυχία ολοκλήρωσης');
      },
    });
  }, [quickCompleteMutation, showToast]);

  // Handle full complete (open modal)
  const handleFullComplete = useCallback((obligation: CalendarObligation) => {
    setSelectedObligation(obligation);
    setIsCompleteModalOpen(true);
  }, []);

  // Handle complete with documents and email
  const handleCompleteAndNotify = useCallback(async (data: {
    file?: File | null;
    documentId?: number | null;
    saveToClientFolder: boolean;
    sendEmail: boolean;
    attachToEmail: boolean;
    emailTemplateId?: number | null;
    notes: string;
    timeSpent?: number | null;
  }) => {
    if (!selectedObligation) return;

    try {
      await completeAndNotifyMutation.mutateAsync({
        obligationId: selectedObligation.id,
        data: {
          file: data.file,
          document_id: data.documentId,
          send_email: data.sendEmail,
          email_template_id: data.emailTemplateId,
          notes: data.notes,
          time_spent: data.timeSpent,
        },
      });
      showToast('success', 'Ολοκληρώθηκε!', data.sendEmail
        ? 'Η υποχρέωση ολοκληρώθηκε και στάλθηκε email'
        : 'Η υποχρέωση ολοκληρώθηκε επιτυχώς'
      );
      setIsCompleteModalOpen(false);
      setSelectedObligation(null);
    } catch (err) {
      showToast('error', 'Σφάλμα', err instanceof Error ? err.message : 'Αποτυχία ολοκλήρωσης');
    }
  }, [selectedObligation, completeAndNotifyMutation, showToast]);

  // Get client info for selected obligation
  const getSelectedClient = useCallback(() => {
    if (!selectedObligation || !clientsData?.results) return null;
    return clientsData.results.find(c => c.id === selectedObligation.client_id);
  }, [selectedObligation, clientsData]);

  // Navigation functions
  const goToPreviousMonth = useCallback(() => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  }, [currentMonth, currentYear]);

  const goToNextMonth = useCallback(() => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  }, [currentMonth, currentYear]);

  const goToToday = useCallback(() => {
    const now = new Date();
    setCurrentMonth(now.getMonth() + 1);
    setCurrentYear(now.getFullYear());
  }, []);

  // Handle day click
  const handleDayClick = useCallback((day: number) => {
    setSelectedDay(day);
  }, []);

  // Close modal
  const closeModal = useCallback(() => {
    setSelectedDay(null);
  }, []);

  // Clear filters
  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const hasActiveFilters = filters.client_id || filters.type_id || filters.status;

  // Keyboard navigation for month
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle if modal is open or typing in input
      if (selectedDay !== null) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goToPreviousMonth();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        goToNextMonth();
      } else if (e.key === 't' || e.key === 'T') {
        e.preventDefault();
        goToToday();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedDay, goToPreviousMonth, goToNextMonth, goToToday]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ημερολόγιο</h1>
          <p className="text-sm text-gray-500">
            Προβολή υποχρεώσεων ανά ημερομηνία προθεσμίας
          </p>
        </div>

        {/* Navigation and actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={goToToday}
            className="px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            Σήμερα
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              hasActiveFilters
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Filter size={16} />
            Φίλτρα
            {hasActiveFilters && (
              <span className="ml-1 px-1.5 py-0.5 bg-blue-600 text-white text-xs rounded-full">
                !
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-gray-900">Φίλτρα</h3>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Καθαρισμός
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Client filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Πελάτης
              </label>
              <select
                value={filters.client_id || ''}
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    client_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Όλοι οι πελάτες</option>
                {clientsData?.results?.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.eponimia}
                  </option>
                ))}
              </select>
            </div>

            {/* Type filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Τύπος υποχρέωσης
              </label>
              <select
                value={filters.type_id || ''}
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    type_id: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Όλοι οι τύποι</option>
                {obligationTypes?.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name} ({type.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Status filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Κατάσταση
              </label>
              <select
                value={filters.status || ''}
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    status: e.target.value || undefined,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Όλες οι καταστάσεις</option>
                <option value="pending">Εκκρεμεί</option>
                <option value="completed">Ολοκληρωμένη</option>
                <option value="overdue">Εκπρόθεσμη</option>
                <option value="in_progress">Σε εξέλιξη</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Month navigation */}
      <div className="flex items-center justify-between bg-white rounded-lg shadow px-4 py-3">
        <button
          onClick={goToPreviousMonth}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          aria-label="Προηγούμενος μήνας"
        >
          <ChevronLeft size={20} className="text-gray-600" />
        </button>

        <h2 className="text-lg font-semibold text-gray-900">
          {GREEK_MONTH_NAMES[currentMonth - 1]} {currentYear}
        </h2>

        <button
          onClick={goToNextMonth}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          aria-label="Επόμενος μήνας"
        >
          <ChevronRight size={20} className="text-gray-600" />
        </button>
      </div>

      {/* Summary stats */}
      {calendarData?.summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Σύνολο</p>
            <p className="text-2xl font-bold text-gray-900">
              {calendarData.summary.total}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Εκκρεμείς</p>
            <p className="text-2xl font-bold text-yellow-600">
              {calendarData.summary.pending}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Ολοκληρωμένες</p>
            <p className="text-2xl font-bold text-green-600">
              {calendarData.summary.completed}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Εκπρόθεσμες</p>
            <p className="text-2xl font-bold text-red-600">
              {calendarData.summary.overdue}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4 col-span-2 md:col-span-1">
            <p className="text-sm text-gray-500">Σε εξέλιξη</p>
            <p className="text-2xl font-bold text-blue-600">
              {calendarData.summary.in_progress}
            </p>
          </div>
        </div>
      )}

      {/* Calendar grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-500">Φόρτωση...</span>
        </div>
      ) : isError ? (
        <div className="bg-red-50 text-red-600 rounded-lg p-4 text-center">
          Σφάλμα φόρτωσης: {(error as Error)?.message || 'Άγνωστο σφάλμα'}
        </div>
      ) : (
        <CalendarGrid
          month={currentMonth}
          year={currentYear}
          days={calendarData?.days || {}}
          onDayClick={handleDayClick}
        />
      )}

      {/* Legend */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Υπόμνημα</h3>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded bg-yellow-100"></span>
            <span className="text-sm text-gray-600">Εκκρεμείς</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded bg-green-100"></span>
            <span className="text-sm text-gray-600">Ολοκληρωμένες</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded bg-red-100"></span>
            <span className="text-sm text-gray-600">Εκπρόθεσμες</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded bg-blue-100"></span>
            <span className="text-sm text-gray-600">Σε εξέλιξη</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-4 rounded ring-2 ring-blue-500"></span>
            <span className="text-sm text-gray-600">Σήμερα</span>
          </div>
        </div>
      </div>

      {/* Day detail modal */}
      <DayDetailModal
        isOpen={selectedDay !== null}
        onClose={closeModal}
        day={selectedDay || 1}
        month={currentMonth}
        year={currentYear}
        dayData={
          selectedDay ? calendarData?.days[String(selectedDay)] : undefined
        }
        onQuickComplete={handleQuickComplete}
        onFullComplete={handleFullComplete}
        isCompleting={quickCompleteMutation.isPending}
      />

      {/* Complete Obligation Modal (full version with documents & email) */}
      <CompleteObligationModal
        isOpen={isCompleteModalOpen}
        onClose={() => {
          setIsCompleteModalOpen(false);
          setSelectedObligation(null);
        }}
        obligation={selectedObligation ? {
          id: selectedObligation.id,
          client_id: selectedObligation.client_id,
          type_code: selectedObligation.type_code,
          type_name: selectedObligation.type_name,
          month: currentMonth,
          year: currentYear,
          status: selectedObligation.status,
        } as unknown as Obligation : null}
        clientName={getSelectedClient()?.eponimia || selectedObligation?.client_name || ''}
        clientEmail={getSelectedClient()?.email || undefined}
        onComplete={handleCompleteAndNotify}
        isLoading={completeAndNotifyMutation.isPending}
      />

      {/* Keyboard shortcuts hint */}
      <div className="text-center text-xs text-gray-400 pb-4">
        <span className="hidden md:inline">
          Συντομεύσεις: <kbd className="px-1 py-0.5 bg-gray-100 rounded">←</kbd> / <kbd className="px-1 py-0.5 bg-gray-100 rounded">→</kbd> για πλοήγηση μηνών, <kbd className="px-1 py-0.5 bg-gray-100 rounded">T</kbd> για σήμερα
        </span>
      </div>
    </div>
  );
}
