import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useDashboardStats, useDashboardRecentActivity, useDashboardCalendar } from '../hooks/useDashboard';
import {
  Users, FileText, AlertCircle, RefreshCw, ArrowRight, Clock, TrendingUp,
  Calendar, CheckCircle, Plus, Activity
} from 'lucide-react';
import { Button, DeadlineListSkeleton } from '../components';
import VoIPWidget from '../components/dashboard/VoIPWidget';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  AreaChart, Area,
} from 'recharts';
import {
  OBLIGATION_STATUS_LABELS_PLURAL,
  GREEK_DAY_NAMES,
} from '../constants';

// Χρώματα καταστάσεων για τα charts — validated παλέτα (CVD-safe, 3:1 contrast):
// το κλασικό κίτρινο/πράσινο/κόκκινο αποτυγχάνει σε πρωτανοπία/δευτερανοπία,
// γι' αυτό τα «εκκρεμή» είναι μπλε
const CHART_STATUS_COLORS: Record<string, string> = {
  completed: '#0ca30c',
  pending: '#3B82F6',
  in_progress: '#7C3AED',
  overdue: '#d03b3b',
  cancelled: '#6B7280',
};

// Κοινό στυλ tooltip για όλα τα charts
const TOOLTIP_STYLE = {
  borderRadius: '0.75rem',
  border: '1px solid #e2e8f0',
  boxShadow: '0 8px 24px rgba(15, 23, 42, 0.12)',
  fontSize: '13px',
  padding: '8px 12px',
};
const AXIS_TICK = { fontSize: 12, fill: '#64748b' };
// Σταθερή σειρά ώστε τα χρώματα να μην «κυκλώνουν» ανάλογα με τα δεδομένα
const CHART_STATUS_ORDER = ['completed', 'in_progress', 'pending', 'overdue', 'cancelled'];

// Κοινή «συνταγή» bento κελιού
const BENTO_CARD = 'bg-white rounded-xl border border-slate-200 shadow-sm';
// Καθυστέρηση εισόδου ανά tile (staggered entrance)
const rise = (i: number): CSSProperties => ({ '--rise-delay': `${i * 50}ms` } as CSSProperties);

export default function Dashboard() {
  const { data: stats, isLoading, isError, error, refetch } = useDashboardStats();
  const { data: recentActivity } = useDashboardRecentActivity(10);
  const { data: calendarData } = useDashboardCalendar();

  const renderStatValue = (value: number | undefined) => {
    if (isLoading) return '...';
    if (isError || value === undefined) return '-';
    return value;
  };

  // Prepare pie chart data from status_breakdown (σταθερή σειρά/χρώμα ανά κατάσταση)
  const pieChartData = stats?.status_breakdown
    ? CHART_STATUS_ORDER.filter((status) => (stats.status_breakdown[status] || 0) > 0)
        .map((status) => ({
          name: OBLIGATION_STATUS_LABELS_PLURAL[status] || status,
          value: stats.status_breakdown[status],
          color: CHART_STATUS_COLORS[status] || '#6B7280',
        }))
    : [];

  // Κατανομή μήνα ανά τύπο με ανάλυση κατάστασης (stacked)
  const typeChartData = stats?.type_breakdown?.map((item) => ({
    name: item.obligation_type__name || 'Άλλο',
    completed: item.completed,
    pending: item.pending,
    overdue: item.overdue,
  })) || [];

  // Φόρτος εργασίας ανά υπάλληλο
  const workloadData = stats?.team_workload?.map((item) => ({
    name: item.name,
    open: item.open,
    overdue: item.overdue,
    completed: item.completed_this_month,
  })) || [];

  // Get current week dates for mini calendar
  const getWeekDates = () => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const monday = new Date(today);
    monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));

    const weekDates = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);
      weekDates.push(date);
    }
    return weekDates;
  };

  const weekDates = getWeekDates();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Get obligation count for a specific date from calendar data
  const getObligationCountForDate = (date: Date): number => {
    if (!calendarData?.events) return 0;
    const dateStr = date.toISOString().split('T')[0];
    const event = calendarData.events.find((e) => e.date === dateStr);
    return event?.count || 0;
  };

  // Format relative time for recent activity
  const formatRelativeTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Μόλις τώρα';
    if (diffMins < 60) return `πριν ${diffMins} λεπτά`;
    if (diffHours < 24) return `πριν ${diffHours} ώρες`;
    if (diffDays === 1) return 'Χθες';
    if (diffDays < 7) return `πριν ${diffDays} ημέρες`;
    return date.toLocaleDateString('el-GR');
  };

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 animate-rise" style={rise(0)}>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Πίνακας Ελέγχου</h1>
          <p className="text-slate-600 text-sm">
            Σήμερα: {new Date().toLocaleDateString('el-GR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        {isError && (
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-1" />
            Ανανέωση
          </Button>
        )}
      </div>

      {/* Error Banner */}
      {isError && (
        <div className="bg-danger-50 border border-danger-200 rounded-xl p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-danger-500 mr-2" />
            <span className="text-danger-700">
              Σφάλμα φόρτωσης δεδομένων: {error instanceof Error ? error.message : 'Άγνωστο σφάλμα'}
            </span>
          </div>
        </div>
      )}

      {/* Bento Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-4">
        {/* Hero tile — Εκκρεμείς υποχρεώσεις μήνα */}
        <Link
          to="/obligations?status=pending"
          className={`${BENTO_CARD} card-lift animate-rise sm:col-span-2 lg:col-span-8 relative overflow-hidden p-6 lg:p-8 bg-gradient-to-br from-brand-50 via-white to-white border-brand-200/70`}
          style={rise(1)}
        >
          <div className="absolute -right-10 -top-10 w-48 h-48 rounded-full bg-brand-100/50 blur-2xl pointer-events-none" aria-hidden="true" />
          <div className="relative flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-brand-700 uppercase tracking-wide">Εκκρεμείς</p>
              <p className="text-6xl lg:text-7xl font-bold text-brand-950 mt-2 tabular-nums leading-none">
                {renderStatValue(stats?.total_obligations_pending)}
              </p>
              <p className="text-sm text-slate-500 mt-3">Υποχρεώσεις σε εκκρεμότητα αυτόν τον μήνα</p>
            </div>
            <div className="p-3 rounded-2xl bg-brand-600 shadow-sm shrink-0">
              <Clock className="w-6 h-6 text-white" />
            </div>
          </div>
          <div className="relative mt-6 inline-flex items-center gap-1 text-sm font-medium text-brand-600">
            Προβολή όλων <ArrowRight className="w-4 h-4" />
          </div>
        </Link>

        {/* Medium stat tiles */}
        <div className="sm:col-span-2 lg:col-span-4 grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-4">
          {[
            {
              label: 'Πελάτες',
              value: stats?.total_clients,
              icon: <Users className="w-5 h-5 text-white" />,
              iconBg: 'bg-brand-600',
              to: '/clients',
              delay: 2,
            },
            {
              label: 'Ολοκληρώθηκαν (μήνας)',
              value: stats?.total_obligations_completed_this_month,
              icon: <TrendingUp className="w-5 h-5 text-white" />,
              iconBg: 'bg-success-600',
              to: '/obligations?status=completed',
              delay: 3,
            },
            {
              label: 'Εκπρόθεσμες',
              value: stats?.overdue_count,
              icon: <AlertCircle className="w-5 h-5 text-white" />,
              iconBg: 'bg-danger-600',
              to: '/obligations?status=overdue',
              delay: 4,
            },
          ].map((tile) => (
            <Link
              key={tile.label}
              to={tile.to}
              className={`${BENTO_CARD} card-lift animate-rise p-5 flex items-center justify-between gap-3`}
              style={rise(tile.delay)}
            >
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-slate-500 truncate">{tile.label}</p>
                <p className="text-3xl font-bold text-slate-900 mt-1 tabular-nums">
                  {renderStatValue(tile.value)}
                </p>
              </div>
              <div className={`p-2.5 rounded-xl ${tile.iconBg} shadow-sm shrink-0`}>
                {tile.icon}
              </div>
            </Link>
          ))}
        </div>

        {/* Status Breakdown Pie Chart */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-5 p-6`} style={rise(5)}>
          <h3 className="text-lg font-semibold text-slate-900">Κατανομή Υποχρεώσεων</h3>
          <p className="text-xs text-slate-500 mb-4">Τρέχων μήνας, ανά κατάσταση</p>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center">
              <div className="w-32 h-32 bg-slate-200 rounded-full animate-pulse" />
            </div>
          ) : pieChartData.length > 0 ? (
            <div className="h-64 relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={62}
                    outerRadius={92}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                    stroke="#fff"
                    strokeWidth={2}
                  >
                    {pieChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(value: number) => [`${value} υποχρεώσεις`, '']}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Σύνολο στο κέντρο του donut */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-3xl font-bold text-slate-900 tabular-nums">
                  {pieChartData.reduce((sum, d) => sum + d.value, 0)}
                </span>
                <span className="text-xs text-slate-500">σύνολο</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
          {/* Legend */}
          <div className="flex flex-wrap justify-center gap-4 mt-4">
            {pieChartData.map((entry, index) => (
              <div key={index} className="flex items-center gap-2">
                <div
                  aria-hidden="true"
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-sm text-slate-600">{entry.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Κατανομή μήνα ανά τύπο (stacked by status) */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-7 p-6`} style={rise(6)}>
          <h3 className="text-lg font-semibold text-slate-900">
            Προθεσμίες Μήνα ανά Τύπο
          </h3>
          <p className="text-xs text-slate-500 mb-4">ΦΠΑ, ΑΠΔ, δηλώσεις κ.λπ. — με ανάλυση κατάστασης</p>
          {isLoading ? (
            <div className="h-64 flex items-end justify-around gap-2 animate-pulse">
              {[70, 50, 85, 40, 60, 45].map((h, i) => (
                <div key={i} className="bg-slate-200 rounded-t flex-1" style={{ height: `${h}%` }} />
              ))}
            </div>
          ) : typeChartData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={typeChartData}
                  layout="vertical"
                  barSize={18}
                  margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#e5e7eb" />
                  <XAxis type="number" allowDecimals={false} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={75} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#f1f5f9' }} />
                  <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 13 }} />
                  <Bar dataKey="completed" name="Ολοκληρωμένες" stackId="s"
                       fill={CHART_STATUS_COLORS.completed} stroke="#fff" strokeWidth={2} />
                  <Bar dataKey="pending" name="Εκκρεμείς" stackId="s"
                       fill={CHART_STATUS_COLORS.pending} stroke="#fff" strokeWidth={2} />
                  <Bar dataKey="overdue" name="Εκπρόθεσμες" stackId="s"
                       fill={CHART_STATUS_COLORS.overdue} stroke="#fff" strokeWidth={2}
                       radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
        </div>

        {/* Επερχόμενες Προθεσμίες — ψηλό κάθετο tile */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-2 lg:col-span-4 lg:row-span-2 p-6`} style={rise(7)}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Clock className="w-5 h-5 text-warning-600" />
              Επερχόμενες Προθεσμίες
            </h3>
            <span className="text-sm text-slate-500">Επόμενες 7 ημέρες</span>
          </div>
          {isLoading ? (
            <DeadlineListSkeleton count={5} />
          ) : stats?.upcoming_deadlines && stats.upcoming_deadlines.length > 0 ? (
            <div className="space-y-3">
              {stats.upcoming_deadlines.slice(0, 5).map((deadline) => (
                <div
                  key={deadline.id}
                  className="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <div>
                    <p className="font-medium text-slate-900">{deadline.client_name}</p>
                    <p className="text-sm text-slate-500">
                      {deadline.type} - {deadline.type_code}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-slate-900">{deadline.deadline}</p>
                    <p className={`text-sm font-medium ${
                      deadline.days_until <= 2 ? 'text-danger-600' : 'text-slate-500'
                    }`}>
                      {deadline.days_until === 0
                        ? 'Σήμερα!'
                        : deadline.days_until === 1
                        ? 'Αύριο'
                        : `Σε ${deadline.days_until} ημέρες`}
                    </p>
                  </div>
                </div>
              ))}
              {stats.upcoming_deadlines.length > 5 && (
                <Link
                  to="/obligations"
                  className="block text-center text-sm text-brand-600 hover:text-brand-700 font-medium py-2"
                >
                  Προβολή όλων ({stats.upcoming_deadlines.length} προθεσμίες)
                </Link>
              )}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-4">
              Δεν υπάρχουν επερχόμενες προθεσμίες τις επόμενες 7 ημέρες.
            </p>
          )}
        </div>

        {/* Φόρτος ανά υπάλληλο */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-8 p-6`} style={rise(8)}>
          <h3 className="text-lg font-semibold text-slate-900">Φόρτος ανά Υπάλληλο</h3>
          <p className="text-xs text-slate-500 mb-4">Ανοιχτές αναθέσεις και απόδοση μήνα</p>
          {isLoading ? (
            <div className="h-64 flex flex-col justify-around gap-2 animate-pulse">
              {[80, 60, 45, 30].map((w, i) => (
                <div key={i} className="bg-slate-200 rounded h-6" style={{ width: `${w}%` }} />
              ))}
            </div>
          ) : workloadData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={workloadData}
                  layout="vertical"
                  barSize={18}
                  margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#e5e7eb" />
                  <XAxis type="number" allowDecimals={false} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={75} tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#f1f5f9' }} />
                  <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 13 }} />
                  <Bar dataKey="completed" name="Ολοκληρωμένες (μήνας)" stackId="w"
                       fill={CHART_STATUS_COLORS.completed} stroke="#fff" strokeWidth={2} />
                  <Bar dataKey="open" name="Ανοιχτές" stackId="w"
                       fill={CHART_STATUS_COLORS.pending} stroke="#fff" strokeWidth={2} />
                  <Bar dataKey="overdue" name="Εκπρόθεσμες" stackId="w"
                       fill={CHART_STATUS_COLORS.overdue} stroke="#fff" strokeWidth={2}
                       radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              Δεν υπάρχουν ανατεθειμένες υποχρεώσεις
            </div>
          )}
        </div>

        {/* Τάση 6 μηνών */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-8 p-6`} style={rise(9)}>
          <h3 className="text-lg font-semibold text-slate-900">Τάση 6 Μηνών</h3>
          <p className="text-xs text-slate-500 mb-4">Σύνολο υποχρεώσεων και ολοκληρώσεις ανά μήνα</p>
          {isLoading ? (
            <div className="h-64 bg-slate-100 rounded animate-pulse" />
          ) : (stats?.monthly_trend?.length || 0) > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={stats!.monthly_trend}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <defs>
                    <linearGradient id="trendTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_STATUS_COLORS.pending} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={CHART_STATUS_COLORS.pending} stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="trendCompleted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_STATUS_COLORS.completed} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={CHART_STATUS_COLORS.completed} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="label" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={AXIS_TICK} width={35} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 13 }} />
                  <Area type="monotone" dataKey="total" name="Σύνολο"
                        stroke={CHART_STATUS_COLORS.pending} strokeWidth={2}
                        fill="url(#trendTotal)"
                        dot={false} activeDot={{ r: 4 }} />
                  <Area type="monotone" dataKey="completed" name="Ολοκληρωμένες"
                        stroke={CHART_STATUS_COLORS.completed} strokeWidth={2}
                        fill="url(#trendCompleted)"
                        dot={false} activeDot={{ r: 4 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
        </div>

        {/* VoIP Widget */}
        <div className="animate-rise sm:col-span-1 lg:col-span-6" style={rise(10)}>
          <VoIPWidget />
        </div>

        {/* Mini Calendar */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-6 p-6`} style={rise(11)}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-brand-600" />
              Εβδομάδα
            </h3>
            <Link
              to="/calendar"
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Πλήρες ημερολόγιο
            </Link>
          </div>
          <div className="grid grid-cols-7 gap-2">
            {/* Day names */}
            {GREEK_DAY_NAMES.map((day) => (
              <div key={day} className="text-center text-xs font-medium text-slate-500 pb-2">
                {day}
              </div>
            ))}
            {/* Week dates */}
            {weekDates.map((date, index) => {
              const isToday = date.getTime() === today.getTime();
              const obligationCount = getObligationCountForDate(date);
              const isPast = date < today;

              return (
                <div
                  key={index}
                  className={`
                    text-center p-2 rounded-lg cursor-pointer transition-colors
                    ${isToday ? 'bg-brand-600 text-white' : 'hover:bg-slate-100'}
                    ${isPast && !isToday ? 'text-slate-400' : ''}
                  `}
                >
                  <div className={`text-sm font-medium ${isToday ? 'text-white' : ''}`}>
                    {date.getDate()}
                  </div>
                  {obligationCount > 0 && (
                    <div
                      className={`
                        text-xs mt-1 px-1.5 py-0.5 rounded-full
                        ${isToday ? 'bg-brand-500 text-white' : 'bg-warning-100 text-warning-700'}
                      `}
                    >
                      {obligationCount}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {/* Calendar summary */}
          {calendarData && (
            <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xl font-bold text-warning-600">{calendarData.pending}</p>
                <p className="text-xs text-slate-500">Εκκρεμείς</p>
              </div>
              <div>
                <p className="text-xl font-bold text-success-600">{calendarData.completed}</p>
                <p className="text-xs text-slate-500">Ολοκληρ.</p>
              </div>
              <div>
                <p className="text-xl font-bold text-danger-600">{calendarData.overdue}</p>
                <p className="text-xs text-slate-500">Εκπρόθεσμες</p>
              </div>
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-6 p-6`} style={rise(12)}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Activity className="w-5 h-5 text-success-600" />
              Πρόσφατη Δραστηριότητα
            </h3>
          </div>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {recentActivity?.recent_completions && recentActivity.recent_completions.length > 0 ? (
              recentActivity.recent_completions.slice(0, 5).map((item) => (
                <div
                  key={`completion-${item.id}`}
                  className="flex items-start gap-3 p-2 hover:bg-slate-50 rounded-lg"
                >
                  <div className="p-1.5 bg-success-100 rounded-full mt-0.5">
                    <CheckCircle className="w-4 h-4 text-success-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {item.client_name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {item.obligation_type} - {item.period}
                    </p>
                  </div>
                  <span className="text-xs text-slate-400 whitespace-nowrap">
                    {item.completed_date ? formatRelativeTime(item.completed_date) : '-'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-slate-500 text-sm text-center py-4">
                Δεν υπάρχει πρόσφατη δραστηριότητα
              </p>
            )}
            {recentActivity?.new_clients && recentActivity.new_clients.length > 0 && (
              <>
                <div className="border-t border-slate-200 my-2"></div>
                {recentActivity.new_clients.slice(0, 3).map((client) => (
                  <div
                    key={`client-${client.id}`}
                    className="flex items-start gap-3 p-2 hover:bg-slate-50 rounded-lg"
                  >
                    <div className="p-1.5 bg-brand-100 rounded-full mt-0.5">
                      <Plus className="w-4 h-4 text-brand-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        Νέος πελάτης: {client.eponimia}
                      </p>
                      <p className="text-xs text-slate-500">ΑΦΜ: {client.afm}</p>
                    </div>
                    <span className="text-xs text-slate-400 whitespace-nowrap">
                      {formatRelativeTime(client.created_at)}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className={`${BENTO_CARD} animate-rise sm:col-span-1 lg:col-span-6 p-6`} style={rise(13)}>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Γρήγορες Ενέργειες</h3>
          <div className="grid grid-cols-1 gap-3">
            <Link
              to="/clients"
              className="flex items-center justify-between p-4 bg-brand-50 rounded-lg hover:bg-brand-100 transition-colors group"
            >
              <div className="flex items-center">
                <Users className="w-5 h-5 text-brand-600 mr-3" />
                <span className="text-brand-950 font-medium">Διαχείριση Πελατών</span>
              </div>
              <ArrowRight className="w-5 h-5 text-brand-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/obligations"
              className="flex items-center justify-between p-4 bg-warning-50 rounded-lg hover:bg-warning-100 transition-colors group"
            >
              <div className="flex items-center">
                <FileText className="w-5 h-5 text-warning-600 mr-3" />
                <span className="text-warning-900 font-medium">Διαχείριση Υποχρεώσεων</span>
              </div>
              <ArrowRight className="w-5 h-5 text-warning-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/calendar"
              className="flex items-center justify-between p-4 bg-success-50 rounded-lg hover:bg-success-100 transition-colors group"
            >
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-success-600 mr-3" />
                <span className="text-success-900 font-medium">Ημερολόγιο Προθεσμιών</span>
              </div>
              <ArrowRight className="w-5 h-5 text-success-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/reports"
              className="flex items-center justify-between p-4 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors group"
            >
              <div className="flex items-center">
                <TrendingUp className="w-5 h-5 text-slate-600 mr-3" />
                <span className="text-slate-900 font-medium">Αναφορές & Στατιστικά</span>
              </div>
              <ArrowRight className="w-5 h-5 text-slate-600 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
