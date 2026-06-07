import { Link } from 'react-router-dom';
import { useDashboardStats, useDashboardRecentActivity, useDashboardCalendar } from '../hooks/useDashboard';
import {
  Users, FileText, AlertCircle, RefreshCw, ArrowRight, Clock, TrendingUp,
  Calendar, CheckCircle, Plus, Activity
} from 'lucide-react';
import { Button, Card, DeadlineListSkeleton } from '../components';
import VoIPWidget from '../components/dashboard/VoIPWidget';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';
import {
  OBLIGATION_STATUS_COLORS_HEX,
  OBLIGATION_STATUS_LABELS_PLURAL,
  GREEK_DAY_NAMES,
} from '../constants';

export default function Dashboard() {
  const { data: stats, isLoading, isError, error, refetch } = useDashboardStats();
  const { data: recentActivity } = useDashboardRecentActivity(10);
  const { data: calendarData } = useDashboardCalendar();

  const renderStatValue = (value: number | undefined) => {
    if (isLoading) return '...';
    if (isError || value === undefined) return '-';
    return value;
  };

  // Prepare pie chart data from status_breakdown
  const pieChartData = stats?.status_breakdown
    ? Object.entries(stats.status_breakdown)
        .filter(([, count]) => count > 0)
        .map(([status, count]) => ({
          name: OBLIGATION_STATUS_LABELS_PLURAL[status] || status,
          value: count,
          color: OBLIGATION_STATUS_COLORS_HEX[status] || '#6B7280',
        }))
    : [];

  // Prepare bar chart data from top_obligation_types
  const barChartData = stats?.top_obligation_types?.slice(0, 6).map((item) => ({
    name: item.obligation_type__name || 'Άλλο',
    count: item.count,
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Πίνακας Ελέγχου</h1>
          <p className="text-gray-600 text-sm">
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
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-500 mr-2" />
            <span className="text-red-700">
              Σφάλμα φόρτωσης δεδομένων: {error instanceof Error ? error.message : 'Άγνωστο σφάλμα'}
            </span>
          </div>
        </div>
      )}

      {/* Quick Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-brand-100">
              <Users className="w-6 h-6 text-brand-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Πελάτες</p>
              <p className="text-2xl font-semibold text-gray-900">
                {renderStatValue(stats?.total_clients)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-yellow-100">
              <Clock className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Εκκρεμείς</p>
              <p className="text-2xl font-semibold text-gray-900">
                {renderStatValue(stats?.total_obligations_pending)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-green-100">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Ολοκληρώθηκαν</p>
              <p className="text-2xl font-semibold text-gray-900">
                {renderStatValue(stats?.total_obligations_completed_this_month)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-red-100">
              <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Εκπρόθεσμες</p>
              <p className="text-2xl font-semibold text-gray-900">
                {renderStatValue(stats?.overdue_count)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Status Breakdown Pie Chart */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Κατανομή Υποχρεώσεων</h3>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center">
              <div className="w-32 h-32 bg-gray-200 rounded-full animate-pulse" />
            </div>
          ) : pieChartData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {pieChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => [`${value} υποχρεώσεις`, '']}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
          {/* Legend */}
          <div className="flex flex-wrap justify-center gap-4 mt-4">
            {pieChartData.map((entry, index) => (
              <div key={index} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-sm text-gray-600">{entry.name}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Top Obligation Types Bar Chart */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Τύποι Υποχρεώσεων</h3>
          {isLoading ? (
            <div className="h-64 flex items-end justify-around gap-2 animate-pulse">
              {[70, 50, 85, 40, 60, 45].map((h, i) => (
                <div key={i} className="bg-gray-200 rounded-t flex-1" style={{ height: `${h}%` }} />
              ))}
            </div>
          ) : barChartData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={barChartData}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                  <XAxis type="number" />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={75}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip formatter={(value: number) => [`${value}`, 'Υποχρεώσεις']} />
                  <Bar dataKey="count" fill="#3B82F6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Δεν υπάρχουν δεδομένα
            </div>
          )}
        </Card>
      </div>

      {/* VoIP Widget and Calendar Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* VoIP Widget */}
        <VoIPWidget />

        {/* Mini Calendar */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
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
              <div key={day} className="text-center text-xs font-medium text-gray-500 pb-2">
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
                    ${isToday ? 'bg-brand-500 text-white' : 'hover:bg-gray-100'}
                    ${isPast && !isToday ? 'text-gray-400' : ''}
                  `}
                >
                  <div className={`text-sm font-medium ${isToday ? 'text-white' : ''}`}>
                    {date.getDate()}
                  </div>
                  {obligationCount > 0 && (
                    <div
                      className={`
                        text-xs mt-1 px-1.5 py-0.5 rounded-full
                        ${isToday ? 'bg-brand-400 text-white' : 'bg-yellow-100 text-yellow-700'}
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
            <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xl font-bold text-yellow-600">{calendarData.pending}</p>
                <p className="text-xs text-gray-500">Εκκρεμείς</p>
              </div>
              <div>
                <p className="text-xl font-bold text-green-600">{calendarData.completed}</p>
                <p className="text-xs text-gray-500">Ολοκληρ.</p>
              </div>
              <div>
                <p className="text-xl font-bold text-red-600">{calendarData.overdue}</p>
                <p className="text-xs text-gray-500">Εκπρόθεσμες</p>
              </div>
            </div>
          )}
        </Card>

        {/* Recent Activity */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Activity className="w-5 h-5 text-green-600" />
              Πρόσφατη Δραστηριότητα
            </h3>
          </div>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {recentActivity?.recent_completions && recentActivity.recent_completions.length > 0 ? (
              recentActivity.recent_completions.slice(0, 5).map((item) => (
                <div
                  key={`completion-${item.id}`}
                  className="flex items-start gap-3 p-2 hover:bg-gray-50 rounded-lg"
                >
                  <div className="p-1.5 bg-green-100 rounded-full mt-0.5">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {item.client_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {item.obligation_type} - {item.period}
                    </p>
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap">
                    {item.completed_date ? formatRelativeTime(item.completed_date) : '-'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-sm text-center py-4">
                Δεν υπάρχει πρόσφατη δραστηριότητα
              </p>
            )}
            {recentActivity?.new_clients && recentActivity.new_clients.length > 0 && (
              <>
                <div className="border-t border-gray-200 my-2"></div>
                {recentActivity.new_clients.slice(0, 3).map((client) => (
                  <div
                    key={`client-${client.id}`}
                    className="flex items-start gap-3 p-2 hover:bg-gray-50 rounded-lg"
                  >
                    <div className="p-1.5 bg-brand-100 rounded-full mt-0.5">
                      <Plus className="w-4 h-4 text-brand-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        Νέος πελάτης: {client.eponimia}
                      </p>
                      <p className="text-xs text-gray-500">ΑΦΜ: {client.afm}</p>
                    </div>
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                      {formatRelativeTime(client.created_at)}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        </Card>
      </div>

      {/* Upcoming Deadlines and Quick Actions Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Upcoming Deadlines */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-5 h-5 text-yellow-600" />
              Επερχόμενες Προθεσμίες
            </h3>
            <span className="text-sm text-gray-500">Επόμενες 7 ημέρες</span>
          </div>
          {isLoading ? (
            <DeadlineListSkeleton count={5} />
          ) : stats?.upcoming_deadlines && stats.upcoming_deadlines.length > 0 ? (
            <div className="space-y-3">
              {stats.upcoming_deadlines.slice(0, 5).map((deadline) => (
                <div
                  key={deadline.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-900">{deadline.client_name}</p>
                    <p className="text-sm text-gray-500">
                      {deadline.type} - {deadline.type_code}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900">{deadline.deadline}</p>
                    <p className={`text-sm font-medium ${
                      deadline.days_until <= 2 ? 'text-red-600' : 'text-gray-500'
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
            <p className="text-gray-500 text-center py-4">
              Δεν υπάρχουν επερχόμενες προθεσμίες τις επόμενες 7 ημέρες.
            </p>
          )}
        </Card>

        {/* Quick Actions */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Γρήγορες Ενέργειες</h3>
          <div className="grid grid-cols-1 gap-3">
            <Link
              to="/clients"
              className="flex items-center justify-between p-4 bg-brand-50 rounded-lg hover:bg-brand-100 transition-colors group"
            >
              <div className="flex items-center">
                <Users className="w-5 h-5 text-brand-600 mr-3" />
                <span className="text-brand-900 font-medium">Διαχείριση Πελατών</span>
              </div>
              <ArrowRight className="w-5 h-5 text-brand-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/obligations"
              className="flex items-center justify-between p-4 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors group"
            >
              <div className="flex items-center">
                <FileText className="w-5 h-5 text-yellow-600 mr-3" />
                <span className="text-yellow-900 font-medium">Διαχείριση Υποχρεώσεων</span>
              </div>
              <ArrowRight className="w-5 h-5 text-yellow-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/calendar"
              className="flex items-center justify-between p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors group"
            >
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-green-600 mr-3" />
                <span className="text-green-900 font-medium">Ημερολόγιο Προθεσμιών</span>
              </div>
              <ArrowRight className="w-5 h-5 text-green-600 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/reports"
              className="flex items-center justify-between p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors group"
            >
              <div className="flex items-center">
                <TrendingUp className="w-5 h-5 text-purple-600 mr-3" />
                <span className="text-purple-900 font-medium">Αναφορές & Στατιστικά</span>
              </div>
              <ArrowRight className="w-5 h-5 text-purple-600 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
