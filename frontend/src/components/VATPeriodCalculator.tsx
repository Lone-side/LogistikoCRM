import { useState, useEffect } from 'react';
import {
  Calculator,
  Lock,
  Unlock,
  RefreshCw,
  ChevronDown,
  AlertCircle,
  CheckCircle,
  Calendar,
  Euro,
  ArrowRight,
  Save,
} from 'lucide-react';
import { Button } from './Button';
import { mydataApi, clientsApi } from '../api/client';
import { MONTH_NAMES as MONTHS, QUARTERS } from '../constants';
import { periodForType } from '../utils/lintBehavior';

// Types
interface Client {
  id: number;
  afm: string;
  eponimia: string;
}

interface VATPeriodResult {
  id: number;
  client: number;
  client_afm: string;
  client_name: string;
  period_type: 'monthly' | 'quarterly';
  year: number;
  period: number;
  period_display: string;
  vat_output: number;
  vat_input: number;
  vat_difference: number;
  previous_credit: number;
  final_result: number;
  credit_to_next: number;
  is_locked: boolean;
  locked_at: string | null;
  is_payable: boolean;
  is_credit: boolean;
  last_calculated_at: string | null;
  created: boolean;  // True if this was a newly created period result
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('el-GR', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount);
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Intl.DateTimeFormat('el-GR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(dateStr));
}

export default function VATPeriodCalculator() {
  // State
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [periodType, setPeriodType] = useState<'monthly' | 'quarterly'>('monthly');
  const [year, setYear] = useState(new Date().getFullYear());
  const [period, setPeriod] = useState(new Date().getMonth() + 1);

  const [loading, setLoading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [result, setResult] = useState<VATPeriodResult | null>(null);
  const [manualCredit, setManualCredit] = useState<string>('');
  const [showCreditInput, setShowCreditInput] = useState(false);

  // Fetch clients on mount
  useEffect(() => {
    const fetchClients = async () => {
      try {
        const response = await clientsApi.getAll({ page_size: 1000 });
        setClients(response.results || response);
      } catch (err) {
        console.error('Error fetching clients:', err);
      }
    };
    fetchClients();
  }, []);

  // Adjust period when period type changes
  useEffect(() => {
    setPeriod((current) => periodForType(current, periodType));
  }, [periodType]);

  // Calculate VAT for selected period
  const handleCalculate = async () => {
    if (!selectedClientId) {
      setError('Επιλέξτε πελάτη');
      return;
    }

    setCalculating(true);
    setError(null);

    try {
      const response = await mydataApi.calculator({
        client_id: selectedClientId,
        period_type: periodType,
        year: year,
        period: period,
        recalculate: true,
      });
      setResult(response);
    } catch (err: unknown) {
      console.error('Calculate error:', err);
      const axiosError = err as { response?: { data?: { error?: string } } };
      setError(axiosError.response?.data?.error || 'Σφάλμα υπολογισμού');
    } finally {
      setCalculating(false);
    }
  };

  // Set manual credit
  const handleSetCredit = async () => {
    if (!result) return;

    const creditValue = parseFloat(manualCredit);
    if (isNaN(creditValue) || creditValue < 0) {
      setError('Εισάγετε έγκυρο ποσό πιστωτικού');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await mydataApi.periods.setCredit(result.id, creditValue);
      // Recalculate to get updated values
      await handleCalculate();
      setShowCreditInput(false);
      setManualCredit('');
    } catch (err: unknown) {
      console.error('Set credit error:', err);
      const axiosError = err as { response?: { data?: { error?: string } } };
      setError(axiosError.response?.data?.error || 'Σφάλμα αποθήκευσης πιστωτικού');
    } finally {
      setSaving(false);
    }
  };

  // Lock/Unlock period
  const handleToggleLock = async () => {
    if (!result) return;

    setLoading(true);
    setError(null);

    try {
      if (result.is_locked) {
        await mydataApi.periods.unlock(result.id);
      } else {
        await mydataApi.periods.lock(result.id);
      }
      // Refresh result
      await handleCalculate();
    } catch (err: unknown) {
      console.error('Lock error:', err);
      const axiosError = err as { response?: { data?: { error?: string } } };
      setError(axiosError.response?.data?.error || 'Σφάλμα κλειδώματος');
    } finally {
      setLoading(false);
    }
  };

  // Generate year options (last 5 years + current)
  const yearOptions = [];
  const currentYear = new Date().getFullYear();
  for (let y = currentYear; y >= currentYear - 5; y--) {
    yearOptions.push(y);
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
            <Calculator size={20} className="text-purple-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Υπολογισμός ΦΠΑ Περιόδου</h3>
            <p className="text-sm text-gray-500">Μηνιαίος/Τριμηνιαίος υπολογισμός με πιστωτικό υπόλοιπο</p>
          </div>
        </div>
      </div>

      {/* Selection Controls */}
      <div className="p-6 border-b border-gray-200 bg-gray-50">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Client Selection */}
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Πελάτης</label>
            <div className="relative">
              <select
                value={selectedClientId || ''}
                onChange={(e) => setSelectedClientId(e.target.value ? Number(e.target.value) : null)}
                className="w-full pl-3 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 appearance-none bg-white"
              >
                <option value="">-- Επιλέξτε Πελάτη --</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.eponimia} ({client.afm})
                  </option>
                ))}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Period Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Τύπος</label>
            <div className="relative">
              <select
                value={periodType}
                onChange={(e) => setPeriodType(e.target.value as 'monthly' | 'quarterly')}
                className="w-full pl-3 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 appearance-none bg-white"
              >
                <option value="monthly">Μηνιαίο</option>
                <option value="quarterly">Τριμηνιαίο</option>
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Year */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Έτος</label>
            <div className="relative">
              <select
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full pl-3 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 appearance-none bg-white"
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Period (Month or Quarter) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {periodType === 'monthly' ? 'Μήνας' : 'Τρίμηνο'}
            </label>
            <div className="relative">
              <select
                value={period}
                onChange={(e) => setPeriod(Number(e.target.value))}
                className="w-full pl-3 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 appearance-none bg-white"
              >
                {periodType === 'monthly' ? (
                  MONTHS.map((month, idx) => (
                    <option key={idx} value={idx + 1}>{month}</option>
                  ))
                ) : (
                  QUARTERS.map((quarter, idx) => (
                    <option key={idx} value={idx + 1}>{quarter}</option>
                  ))
                )}
              </select>
              <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Calculate Button */}
        <div className="mt-4 flex justify-end">
          <Button
            onClick={handleCalculate}
            disabled={calculating || !selectedClientId}
            className="bg-purple-600 hover:bg-purple-700"
          >
            {calculating ? (
              <>
                <RefreshCw size={18} className="mr-2 animate-spin" />
                Υπολογισμός...
              </>
            ) : (
              <>
                <Calculator size={18} className="mr-2" />
                Υπολογισμός ΦΠΑ
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertCircle size={20} className="text-red-500 flex-shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="p-6 space-y-6">
          {/* Period Info & Lock Status */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <Calendar size={20} className="text-gray-400" />
              <div>
                <p className="font-semibold text-gray-900">
                  {result.client_name} - {result.period_display}
                </p>
                <p className="text-sm text-gray-500">ΑΦΜ: {result.client_afm}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {result.is_locked ? (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-100 text-red-700 text-sm rounded-full">
                  <Lock size={14} />
                  Κλειδωμένο
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full">
                  <Unlock size={14} />
                  Ανοιχτό
                </span>
              )}
              <Button
                onClick={handleToggleLock}
                disabled={loading}
                variant="secondary"
                size="sm"
              >
                {result.is_locked ? (
                  <>
                    <Unlock size={16} className="mr-1" />
                    Ξεκλείδωμα
                  </>
                ) : (
                  <>
                    <Lock size={16} className="mr-1" />
                    Κλείδωμα
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* VAT Calculation Display */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* ΦΠΑ Εκροών */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <p className="text-sm text-green-600 mb-1">ΦΠΑ Εκροών (Πωλήσεις)</p>
              <p className="text-2xl font-bold text-green-700">{formatCurrency(result.vat_output)}</p>
            </div>

            {/* ΦΠΑ Εισροών */}
            <div className="bg-red-50 rounded-lg p-4 border border-red-200">
              <p className="text-sm text-red-600 mb-1">ΦΠΑ Εισροών (Αγορές)</p>
              <p className="text-2xl font-bold text-red-700">{formatCurrency(result.vat_input)}</p>
            </div>

            {/* Διαφορά */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <p className="text-sm text-blue-600 mb-1">Διαφορά (Εκροές - Εισροές)</p>
              <p className={`text-2xl font-bold ${result.vat_difference >= 0 ? 'text-blue-700' : 'text-purple-700'}`}>
                {formatCurrency(result.vat_difference)}
              </p>
            </div>
          </div>

          {/* Credit Calculation Flow */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-4">Υπολογισμός με Πιστωτικό Υπόλοιπο</h4>

            <div className="flex flex-col sm:flex-row items-center gap-4 text-center">
              {/* Previous Credit */}
              <div className="flex-1 w-full sm:w-auto">
                <p className="text-xs text-gray-500 mb-1">Πιστωτικό Προηγούμενης</p>
                <div className="flex items-center justify-center gap-2">
                  <p className="text-lg font-semibold text-purple-600">
                    {formatCurrency(result.previous_credit)}
                  </p>
                  {/* Show edit button only if unlocked AND (new period OR no credit yet) */}
                  {!result.is_locked && (result.created || result.previous_credit === 0) && (
                    <button
                      onClick={() => {
                        setShowCreditInput(!showCreditInput);
                        setManualCredit(result.previous_credit.toString());
                      }}
                      className="text-purple-500 hover:text-purple-700"
                      title="Ορισμός πιστωτικού"
                    >
                      <Save size={14} />
                    </button>
                  )}
                </div>
                {result.previous_credit > 0 && !result.created && (
                  <p className="text-xs text-purple-400 mt-1">Από προηγούμενη περίοδο</p>
                )}
              </div>

              <ArrowRight size={20} className="text-gray-400 hidden sm:block" />

              {/* Difference */}
              <div className="flex-1 w-full sm:w-auto">
                <p className="text-xs text-gray-500 mb-1">Διαφορά ΦΠΑ</p>
                <p className="text-lg font-semibold text-gray-700">
                  {formatCurrency(result.vat_difference)}
                </p>
              </div>

              <ArrowRight size={20} className="text-gray-400 hidden sm:block" />

              {/* Final Result */}
              <div className="flex-1 w-full sm:w-auto bg-white rounded-lg p-3 border-2 border-yellow-400">
                <p className="text-xs text-gray-500 mb-1">
                  {result.is_payable ? 'Προς Απόδοση' : 'Πιστωτικό Υπόλοιπο'}
                </p>
                <p className={`text-xl font-bold ${result.is_payable ? 'text-yellow-600' : 'text-purple-600'}`}>
                  {formatCurrency(Math.abs(result.final_result))}
                </p>
              </div>

              {result.credit_to_next > 0 && (
                <>
                  <ArrowRight size={20} className="text-gray-400 hidden sm:block" />
                  <div className="flex-1 w-full sm:w-auto">
                    <p className="text-xs text-gray-500 mb-1">Μεταφορά Επόμενης</p>
                    <p className="text-lg font-semibold text-purple-600">
                      {formatCurrency(result.credit_to_next)}
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Manual Credit Input */}
            {showCreditInput && !result.is_locked && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Πιστωτικό Προηγούμενης Περιόδου (€)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={manualCredit}
                      onChange={(e) => setManualCredit(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                      placeholder="0.00"
                    />
                  </div>
                  <Button
                    onClick={handleSetCredit}
                    disabled={saving}
                    className="bg-purple-600 hover:bg-purple-700"
                  >
                    {saving ? 'Αποθήκευση...' : 'Αποθήκευση'}
                  </Button>
                  <Button
                    onClick={() => setShowCreditInput(false)}
                    variant="secondary"
                  >
                    Ακύρωση
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Summary Box */}
          <div className={`rounded-lg p-6 border-2 ${
            result.is_payable
              ? 'bg-yellow-50 border-yellow-300'
              : 'bg-purple-50 border-purple-300'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                  result.is_payable ? 'bg-yellow-200' : 'bg-purple-200'
                }`}>
                  <Euro size={24} className={result.is_payable ? 'text-yellow-700' : 'text-purple-700'} />
                </div>
                <div>
                  <p className={`text-sm ${result.is_payable ? 'text-yellow-600' : 'text-purple-600'}`}>
                    {result.is_payable ? 'ΦΠΑ προς Απόδοση' : 'Πιστωτικό Υπόλοιπο'}
                  </p>
                  <p className={`text-3xl font-bold ${result.is_payable ? 'text-yellow-700' : 'text-purple-700'}`}>
                    {formatCurrency(Math.abs(result.final_result))}
                  </p>
                </div>
              </div>
              <div className="text-right">
                {result.last_calculated_at && (
                  <p className="text-xs text-gray-500">
                    Τελ. υπολογισμός: {formatDateTime(result.last_calculated_at)}
                  </p>
                )}
                {result.is_locked && result.locked_at && (
                  <p className="text-xs text-gray-500">
                    Κλειδώθηκε: {formatDateTime(result.locked_at)}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Info Message */}
          <div className="flex items-start gap-3 text-sm text-gray-500">
            <CheckCircle size={18} className="text-green-500 flex-shrink-0 mt-0.5" />
            <p>
              {result.is_locked
                ? 'Η περίοδος είναι κλειδωμένη. Για αλλαγές, ξεκλειδώστε πρώτα.'
                : 'Κλειδώστε την περίοδο μετά την υποβολή της δήλωσης για να προστατέψετε τα δεδομένα.'
              }
            </p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!result && !error && (
        <div className="p-12 text-center text-gray-500">
          <Calculator size={48} className="mx-auto mb-4 text-gray-300" />
          <p>Επιλέξτε πελάτη και περίοδο για να υπολογίσετε το ΦΠΑ</p>
        </div>
      )}
    </div>
  );
}
