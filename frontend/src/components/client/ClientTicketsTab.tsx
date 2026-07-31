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
        <h3 className="text-sm font-medium text-slate-700">
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
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-slate-400" />
        </div>
      )}

      {/* Table */}
      {!isLoading && data && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                  Τίτλος
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                  Κατάσταση
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                  Προτεραιότητα
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                  Ανατέθηκε
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">
                  Δημιουργία
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase">
                  Ενέργειες
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {data.tickets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    Δεν υπάρχουν tickets
                  </td>
                </tr>
              ) : (
                data.tickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-slate-900">{ticket.title}</p>
                      {ticket.description && (
                        <p className="text-xs text-slate-500 truncate max-w-xs">
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
                          className="text-xs border border-slate-200 rounded px-2 py-1 focus:ring-2 focus:ring-brand-500"
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
                              ? 'bg-brand-100 text-brand-800'
                              : 'bg-slate-100 text-slate-800'
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
                          className="text-xs border border-slate-200 rounded px-2 py-1 focus:ring-2 focus:ring-brand-500"
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
                            PRIORITY_COLORS[ticket.priority] || 'bg-slate-100'
                          }`}
                        >
                          {ticket.priority_display || ticket.priority}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {ticket.assigned_to_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {new Date(ticket.created_at).toLocaleDateString('el-GR')}
                      <span className="text-xs text-slate-400 ml-1">
                        ({ticket.days_since_created} μέρες)
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {confirmDeleteId === ticket.id ? (
                        <div className="flex items-center justify-end gap-2">
                          <span className="text-xs text-danger-600">Διαγραφή;</span>
                          <button
                            onClick={() => handleDeleteConfirm(ticket.id)}
                            disabled={isDeleting}
                            className="px-2 py-1 text-xs bg-danger-600 text-white rounded hover:bg-danger-700 disabled:opacity-50"
                          >
                            Ναι
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded hover:bg-slate-200"
                          >
                            Όχι
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          {editingTicketId === ticket.id ? (
                            <button
                              onClick={() => setEditingTicketId(null)}
                              className="p-1 text-success-600 hover:bg-success-50 rounded"
                              title="Κλείσιμο"
                              aria-label="Κλείσιμο"
                            >
                              <CheckCircle className="w-4 h-4" />
                            </button>
                          ) : (
                            <button
                              onClick={() => setEditingTicketId(ticket.id)}
                              className="p-1 text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded"
                              title="Επεξεργασία"
                              aria-label="Επεξεργασία"
                            >
                              <Pencil className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => setConfirmDeleteId(ticket.id)}
                            className="p-1 text-slate-400 hover:text-danger-600 hover:bg-danger-50 rounded"
                            title="Διαγραφή"
                            aria-label="Διαγραφή"
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
