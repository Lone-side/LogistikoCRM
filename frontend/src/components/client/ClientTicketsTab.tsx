import { useState } from 'react';
import {
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  CheckCircle,
} from 'lucide-react';
import { Button } from '../../components';
import type { VoIPTicket } from '../../types';
import { PRIORITY_COLORS } from '../../constants';

// Ticket status options
const TICKET_STATUS_OPTIONS = [
  { value: 'open', label: 'Ανοιχτό' },
  { value: 'in_progress', label: 'Σε εξέλιξη' },
  { value: 'resolved', label: 'Επιλύθηκε' },
  { value: 'closed', label: 'Κλειστό' },
];

// Ticket priority options
const TICKET_PRIORITY_OPTIONS = [
  { value: 'low', label: 'Χαμηλή' },
  { value: 'medium', label: 'Μέτρια' },
  { value: 'high', label: 'Υψηλή' },
  { value: 'urgent', label: 'Επείγον' },
];

// Ticket update data type
export type TicketUpdateData = {
  status?: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
};

// Props interface
export interface ClientTicketsTabProps {
  data: { tickets: VoIPTicket[] } | undefined;
  isLoading: boolean;
  onCreate: () => void;
  onUpdate: (ticketId: number, data: TicketUpdateData) => void;
  onDelete: (ticketId: number) => void;
  isUpdating: boolean;
  isDeleting: boolean;
}

export default function ClientTicketsTab({
  data,
  isLoading,
  onCreate,
  onUpdate,
  onDelete,
  isUpdating,
  isDeleting,
}: ClientTicketsTabProps) {
  const [editingTicketId, setEditingTicketId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const handleStatusChange = (ticketId: number, newStatus: string) => {
    onUpdate(ticketId, { status: newStatus as 'open' | 'in_progress' | 'resolved' | 'closed' });
  };

  const handlePriorityChange = (ticketId: number, newPriority: string) => {
    onUpdate(ticketId, { priority: newPriority as 'low' | 'medium' | 'high' | 'urgent' });
  };

  const handleDeleteConfirm = (ticketId: number) => {
    onDelete(ticketId);
    setConfirmDeleteId(null);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-medium text-gray-700">
          {data ? `${data.tickets.length} tickets` : 'Tickets'}
        </h3>
        <Button onClick={onCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Νέο Ticket
        </Button>
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
                  Τίτλος
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Κατάσταση
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Προτεραιότητα
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Ανατέθηκε
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Δημιουργία
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Ενέργειες
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.tickets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    Δεν υπάρχουν tickets
                  </td>
                </tr>
              ) : (
                data.tickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900">{ticket.title}</p>
                      {ticket.description && (
                        <p className="text-xs text-gray-500 truncate max-w-xs">
                          {ticket.description}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {editingTicketId === ticket.id ? (
                        <select
                          value={ticket.status}
                          onChange={(e) => handleStatusChange(ticket.id, e.target.value)}
                          disabled={isUpdating}
                          className="text-xs border border-gray-200 rounded px-2 py-1 focus:ring-2 focus:ring-brand-500"
                        >
                          {TICKET_STATUS_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded ${
                            ticket.is_open
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {ticket.status_display || ticket.status}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {editingTicketId === ticket.id ? (
                        <select
                          value={ticket.priority}
                          onChange={(e) => handlePriorityChange(ticket.id, e.target.value)}
                          disabled={isUpdating}
                          className="text-xs border border-gray-200 rounded px-2 py-1 focus:ring-2 focus:ring-brand-500"
                        >
                          {TICKET_PRIORITY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded ${
                            PRIORITY_COLORS[ticket.priority] || 'bg-gray-100'
                          }`}
                        >
                          {ticket.priority_display || ticket.priority}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {ticket.assigned_to_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {new Date(ticket.created_at).toLocaleDateString('el-GR')}
                      <span className="text-xs text-gray-400 ml-1">
                        ({ticket.days_since_created} μέρες)
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {confirmDeleteId === ticket.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <span className="text-xs text-red-600">Διαγραφή;</span>
                          <button
                            onClick={() => handleDeleteConfirm(ticket.id)}
                            disabled={isDeleting}
                            className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                          >
                            Ναι
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                          >
                            Όχι
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          {editingTicketId === ticket.id ? (
                            <button
                              onClick={() => setEditingTicketId(null)}
                              className="p-1 text-green-600 hover:bg-green-50 rounded"
                              title="Κλείσιμο"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                          ) : (
                            <button
                              onClick={() => setEditingTicketId(ticket.id)}
                              className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                              title="Επεξεργασία"
                            >
                              <Pencil className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => setConfirmDeleteId(ticket.id)}
                            className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                            title="Διαγραφή"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
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
