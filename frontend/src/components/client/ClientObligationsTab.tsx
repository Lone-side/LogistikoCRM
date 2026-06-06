import { Link } from 'react-router-dom';
import { RefreshCw, ExternalLink } from 'lucide-react';
import {
  OBLIGATION_STATUS_COLORS as STATUS_COLORS,
  OBLIGATION_STATUS_LABELS as STATUS_LABELS,
} from '../../constants';

// Obligation item interface
export interface ObligationItem {
  id: number;
  obligation_type_name?: string;
  obligation_type_code?: string;
  year: number;
  month: number;
  deadline: string;
  status: string;
  completed_date?: string | null;
  notes?: string;
}

// Props interface
export interface ClientObligationsTabProps {
  clientId: number;
  data: { obligations: ObligationItem[] } | undefined;
  isLoading: boolean;
  yearFilter: number;
  setYearFilter: (year: number) => void;
  statusFilter: string;
  setStatusFilter: (status: string) => void;
}

export default function ClientObligationsTab({
  clientId,
  data,
  isLoading,
  yearFilter,
  setYearFilter,
  statusFilter,
  setStatusFilter,
}: ClientObligationsTabProps) {
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - i);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Έτος:</label>
          <select
            value={yearFilter}
            onChange={(e) => setYearFilter(Number(e.target.value))}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="obl-status-filter" className="text-sm text-gray-600">Κατάσταση:</label>
          <select
            id="obl-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm"
            aria-label="Φίλτρο κατάστασης υποχρεώσεων"
          >
            <option value="">Όλες</option>
            <option value="pending">Εκκρεμείς</option>
            <option value="completed">Ολοκληρωμένες</option>
            <option value="overdue">Καθυστερημένες</option>
          </select>
        </div>
        <Link
          to={`/obligations?client=${clientId}`}
          className="ml-auto text-sm text-blue-600 hover:underline"
        >
          Προβολή όλων
          <ExternalLink className="w-3 h-3 inline ml-1" />
        </Link>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
        </div>
      )}

      {/* Table */}
      {!isLoading && data && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Τύπος
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Περίοδος
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Προθεσμία
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Κατάσταση
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Ολοκλήρωση
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.obligations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    Δεν βρέθηκαν υποχρεώσεις
                  </td>
                </tr>
              ) : (
                data.obligations.map((obl) => (
                  <tr key={obl.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">
                      <Link
                        to={`/obligations?id=${obl.id}`}
                        className="text-blue-600 hover:underline font-medium"
                      >
                        {obl.obligation_type_name || obl.obligation_type_code}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {String(obl.month).padStart(2, '0')}/{obl.year}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {new Date(obl.deadline).toLocaleDateString('el-GR')}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          STATUS_COLORS[obl.status] || 'bg-gray-100'
                        }`}
                      >
                        {STATUS_LABELS[obl.status] || obl.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {obl.completed_date
                        ? new Date(obl.completed_date).toLocaleDateString('el-GR')
                        : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
