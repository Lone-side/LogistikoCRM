import { useState } from 'react';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Calendar,
  Download,
  Users,
  ClipboardList,
  RefreshCw,
  AlertCircle,
  FileSpreadsheet,
  FileText,
  Loader2,
} from 'lucide-react';
import { Button } from '../components';
import {
  useReportsStats,
  useReportsExport,
  useReportExport,
  type ReportPeriod
} from '../hooks/useReports';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: 'today', label: 'Σήμερα' },
  { value: 'week', label: 'Εβδομάδα' },
  { value: 'month', label: 'Μήνας' },
  { value: 'quarter', label: 'Τρίμηνο' },
  { value: 'year', label: 'Έτος' },
];

const TYPE_COLORS: Record<string, string> = {
  'ΦΠΑ': 'bg-blue-500',
  'ΑΠΔ': 'bg-green-500',
  'ΕΝΦΙΑ': 'bg-yellow-500',
  'Ε1': 'bg-purple-500',
  'Ε3': 'bg-pink-500',
  'ΜΥΦ': 'bg-orange-500',
};

export default function Reports() {
  const [period, setPeriod] = useState<ReportPeriod>('month');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const { data: stats, isLoading, isError, error, refetch } = useReportsStats(period);
  useReportsExport();
  const {
    isExporting,
    exportType,
    exportClients,
    exportObligations,
    exportMonthlyPdf,
  } = useReportExport();

  // Get current date for monthly PDF export
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  const handleExport = async (type: string) => {
    setShowExportMenu(false);
    try {
      if (type === 'clients') {
        await exportClients();
      } else if (type === 'obligations') {
        await exportObligations(period);
      } else if (type === 'monthly-pdf') {
        await exportMonthlyPdf(currentYear, currentMonth);
      }
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  const renderStatValue = (value: number | undefined) => {
    if (isLoading) return '...';
    if (isError || value === undefined) return '-';
    return value.toLocaleString('el-GR');
  };

  const renderChange = (change: number | undefined, inverted = false) => {
    if (change === undefined || change === 0) return null;

    const isPositive = inverted ? change < 0 : change > 0;
    const Icon = isPositive ? TrendingUp : TrendingDown;
    const colorClass = isPositive ? 'text-green-600' : 'text-red-600';
    const sign = change > 0 ? '+' : '';

    return (
      <div className={`flex items-center gap-1 text-sm ${colorClass}`}>
        <Icon size={16} />
        <span>{sign}{change}%</span>
      </div>
    );
  };

  // Get max count for percentage calculation in bar chart
  const maxTypeCount = stats?.obligations_by_type?.length
    ? Math.max(...stats.obligations_by_type.map(t => t.count))
    : 1;

  // Get color for obligation type
  const getTypeColor = (code: string): string => {
    return TYPE_COLORS[code] || 'bg-gray-500';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Αναφορές</h1>
          <p className="text-gray-500 mt-1">Στατιστικά και αναλύσεις</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw size={18} className={`mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Ανανέωση
          </Button>
          {/* Export dropdown */}
          <div className="relative">
            <Button
              onClick={() => setShowExportMenu(!showExportMenu)}
              disabled={isExporting}
            >
              {isExporting ? (
                <Loader2 size={18} className="mr-2 animate-spin" />
              ) : (
                <Download size={18} className="mr-2" />
              )}
              {isExporting ? 'Εξαγωγή...' : 'Εξαγωγή'}
            </Button>
            {showExportMenu && (
              <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
                <button
                  onClick={() => handleExport('clients')}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
                >
                  <FileSpreadsheet size={18} className="text-green-600" />
                  <div>
                    <div className="font-medium text-sm">Πελάτες (Excel)</div>
                    <div className="text-xs text-gray-500">Πλήρης λίστα πελατών</div>
                  </div>
                </button>
                <button
                  onClick={() => handleExport('obligations')}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
                >
                  <FileSpreadsheet size={18} className="text-blue-600" />
                  <div>
                    <div className="font-medium text-sm">Υποχρεώσεις (Excel)</div>
                    <div className="text-xs text-gray-500">Τρέχουσες υποχρεώσεις</div>
                  </div>
                </button>
                <button
                  onClick={() => handleExport('monthly-pdf')}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
                >
                  <FileText size={18} className="text-red-600" />
                  <div>
                    <div className="font-medium text-sm">Μηνιαία Αναφορά (PDF)</div>
                    <div className="text-xs text-gray-500">
                      {currentMonth}/{currentYear}
                    </div>
                  </div>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-500 mr-2" />
            <span className="text-red-700">
              Σφάλμα φόρτωσης δεδομένων: {error instanceof Error ? error.message : 'Άγνωστο σφάλμα'}
            </span>
          </div>
        </div>
      )}

      {/* Date Range Selector */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar size={18} className="text-gray-400" />
            <span className="text-sm text-gray-600">Περίοδος:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setPeriod(option.value)}
                className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                  period === option.value
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Users size={24} className="text-blue-600" />
            </div>
            {renderChange(stats?.comparison?.clients_change)}
          </div>
          <p className="text-sm text-gray-500 mb-1">Συνολικοί πελάτες</p>
          <p className="text-2xl font-bold text-gray-900">{renderStatValue(stats?.total_clients)}</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <ClipboardList size={24} className="text-green-600" />
            </div>
            {renderChange(stats?.comparison?.completed_change)}
          </div>
          <p className="text-sm text-gray-500 mb-1">Ολοκληρωμένες</p>
          <p className="text-2xl font-bold text-gray-900">{renderStatValue(stats?.completed_obligations)}</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <ClipboardList size={24} className="text-yellow-600" />
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-1">Σε εκκρεμότητα</p>
          <p className="text-2xl font-bold text-gray-900">{renderStatValue(stats?.pending_obligations)}</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <ClipboardList size={24} className="text-red-600" />
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-1">Εκπρόθεσμες</p>
          <p className="text-2xl font-bold text-gray-900">{renderStatValue(stats?.overdue_obligations)}</p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Obligations by Type */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Υποχρεώσεις ανά τύπο</h3>
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : stats?.obligations_by_type && stats.obligations_by_type.length > 0 ? (
            <div className="space-y-4">
              {stats.obligations_by_type.slice(0, 8).map((item) => (
                <div key={item.obligation_type__code || item.obligation_type__name}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">
                      {item.obligation_type__code || item.obligation_type__name}
                    </span>
                    <span className="text-gray-900 font-medium">{item.count}</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getTypeColor(item.obligation_type__code)} rounded-full transition-all`}
                      style={{ width: `${(item.count / maxTypeCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
        </div>

        {/* Monthly Activity */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Μηνιαία δραστηριότητα</h3>
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : stats?.monthly_activity && stats.monthly_activity.length > 0 ? (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={stats.monthly_activity}
                  margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 12 }}
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 12 }} width={40} />
                  <Tooltip
                    formatter={(value: number) => [`${value} ολοκληρώθηκαν`, '']}
                    labelFormatter={(label) => `Μήνας: ${label}`}
                  />
                  <Bar dataKey="count" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
        </div>
      </div>

      {/* Completion Rate Card */}
      {stats && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Ποσοστό Ολοκλήρωσης</h3>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{ width: `${stats.completion_rate}%` }}
                />
              </div>
            </div>
            <span className="text-2xl font-bold text-gray-900">{stats.completion_rate}%</span>
          </div>
          <p className="text-sm text-gray-500 mt-2">
            {stats.completed_obligations} ολοκληρωμένες από συνολικά{' '}
            {stats.completed_obligations + stats.pending_obligations + stats.overdue_obligations} υποχρεώσεις
          </p>
        </div>
      )}

      {/* Reports List */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Διαθέσιμες αναφορές</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {[
            { name: 'Αναφορά πελατών', description: 'Πλήρης λίστα πελατών με στοιχεία επικοινωνίας', type: 'clients', enabled: true },
            { name: 'Αναφορά υποχρεώσεων', description: 'Κατάσταση υποχρεώσεων ανά μήνα', type: 'obligations', enabled: true },
            { name: 'Μηνιαία αναφορά (PDF)', description: `Συνοπτική αναφορά ${currentMonth}/${currentYear}`, type: 'monthly-pdf', enabled: true },
            { name: 'Οικονομική αναφορά', description: 'Έσοδα και στατιστικά χρεώσεων (σύντομα)', type: 'financial', enabled: false },
            { name: 'Αναφορά απόδοσης', description: 'Χρόνοι ολοκλήρωσης και KPIs (σύντομα)', type: 'performance', enabled: false },
          ].map((report, index) => {
            const IconComponent = report.type === 'clients' ? Users :
                                  report.type === 'obligations' ? ClipboardList :
                                  report.type === 'monthly-pdf' ? FileText :
                                  report.type === 'financial' ? TrendingUp : BarChart3;
            const isCurrentlyExporting = isExporting && exportType === report.type;
            return (
              <div key={index} className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    report.enabled ? 'bg-gray-100' : 'bg-gray-50'
                  }`}>
                    <IconComponent size={20} className={report.enabled ? 'text-gray-600' : 'text-gray-400'} />
                  </div>
                  <div>
                    <p className={`font-medium ${report.enabled ? 'text-gray-900' : 'text-gray-400'}`}>
                      {report.name}
                    </p>
                    <p className="text-sm text-gray-500">{report.description}</p>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleExport(report.type)}
                  disabled={!report.enabled || isExporting}
                >
                  {isCurrentlyExporting ? (
                    <Loader2 size={16} className="mr-2 animate-spin" />
                  ) : (
                    <Download size={16} className="mr-2" />
                  )}
                  {isCurrentlyExporting ? 'Λήψη...' : 'Λήψη'}
                </Button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
