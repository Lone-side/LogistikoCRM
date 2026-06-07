import {
  RefreshCw,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
} from 'lucide-react';

// Call interface
export interface CallItem {
  id: number;
  phone_number: string;
  direction: string;
  direction_display?: string;
  status: string;
  status_display?: string;
  started_at: string | null;
  duration_formatted?: string;
  notes?: string;
}

// Props interface
export interface ClientCallsTabProps {
  data: { calls: CallItem[] } | undefined;
  isLoading: boolean;
}

export default function ClientCallsTab({
  data,
  isLoading,
}: ClientCallsTabProps) {
  const getCallIcon = (direction: string, status: string) => {
    if (status === 'missed') return <PhoneMissed className="w-4 h-4 text-red-500" />;
    if (direction === 'incoming') return <PhoneIncoming className="w-4 h-4 text-green-500" />;
    return <PhoneOutgoing className="w-4 h-4 text-brand-500" />;
  };

  return (
    <div className="space-y-4">
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
                  Αριθμός
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Ημερομηνία
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Διάρκεια
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Σημειώσεις
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.calls.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    Δεν υπάρχουν καταγεγραμμένες κλήσεις
                  </td>
                </tr>
              ) : (
                data.calls.map((call) => (
                  <tr key={call.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {getCallIcon(call.direction, call.status)}
                        <span className="text-sm">
                          {call.direction_display || call.direction}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm font-mono">{call.phone_number}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {call.started_at
                        ? new Date(call.started_at).toLocaleString('el-GR')
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {call.duration_formatted || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 truncate max-w-xs">
                      {call.notes || '-'}
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
