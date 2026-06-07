import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Ticket,
  Search,
  Filter,
  Plus,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  X,
  Phone,
  Edit,
  Check,
  Clock,
  AlertCircle,
  User,
} from 'lucide-react';
import { Button } from '../components';
import {
  useTickets,
  useCreateTicket,
  useChangeTicketStatus,
  useUpdateTicket,
  useDeleteTicket,
  type TicketsFilters,
} from '../hooks/useTickets';
import { useDebounce } from '../hooks/useDebounce';
import { useUsers } from '../hooks/useUsers';
import { useClients } from '../hooks/useClients';
import type { TicketFull } from '../types';
import {
  TICKET_STATUS_OPTIONS as STATUS_OPTIONS,
  PRIORITY_OPTIONS,
  TICKET_STATUS_COLORS as STATUS_COLORS,
  TICKET_STATUS_LABELS as STATUS_LABELS,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
} from '../constants';

export default function Tickets() {
  // Filters state
  const [filters, setFilters] = useState<TicketsFilters>({
    page: 1,
    page_size: 20,
  });
  const [showFilters, setShowFilters] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearchInput = useDebounce(searchInput, 300);

  // Modal states
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState<TicketFull | null>(null);

  // Data fetching
  const { data, isLoading, isError, refetch } = useTickets(filters);
  const { data: clientsData } = useClients({ page_size: 1000 }); // Get all clients for dropdown
  const clients = clientsData?.results || [];

  // Auto-search when debounced search input changes
  useEffect(() => {
    setFilters((prev) => ({
      ...prev,
      search: debouncedSearchInput || undefined,
      page: 1,
    }));
  }, [debouncedSearchInput]);

  // Handlers
  const handleFilterChange = useCallback(
    (key: keyof TicketsFilters, value: string | boolean | number | undefined) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value || undefined,
        page: 1, // Reset to first page on filter change
      }));
    },
    []
  );

  const handleClearFilters = useCallback(() => {
    setFilters({ page: 1, page_size: 20 });
    setSearchInput('');
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }));
  }, []);

  const handleOpenDetail = useCallback((ticket: TicketFull) => {
    setSelectedTicket(ticket);
    setDetailModalOpen(true);
  }, []);

  // Calculate pagination
  const totalPages = data ? Math.ceil(data.count / (filters.page_size || 20)) : 0;
  const currentPage = filters.page || 1;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tickets</h1>
          <p className="text-gray-500 mt-1">Διαχείριση αιτημάτων και εργασιών</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw size={18} className={`mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Ανανέωση
          </Button>
          <Button onClick={() => setCreateModalOpen(true)}>
            <Plus size={18} className="mr-2" />
            Νέο Ticket
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Ticket size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Σύνολο</p>
              <p className="text-xl font-bold text-gray-900">{data?.stats?.total || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <AlertCircle size={20} className="text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Ανοιχτά</p>
              <p className="text-xl font-bold text-gray-900">{data?.stats?.open || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Clock size={20} className="text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Σε εξέλιξη</p>
              <p className="text-xl font-bold text-gray-900">{data?.stats?.in_progress || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Check size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Επιλύθηκαν</p>
              <p className="text-xl font-bold text-gray-900">{data?.stats?.resolved || 0}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
              <X size={20} className="text-gray-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Κλειστά</p>
              <p className="text-xl font-bold text-gray-900">{data?.stats?.closed || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Αναζήτηση με τίτλο ή πελάτη..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors ${
              showFilters ? 'border-blue-500 text-blue-600 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
            }`}
          >
            <Filter size={18} />
            <span>Φίλτρα</span>
          </button>
          {(filters.status || filters.priority || filters.search || filters.open_only || filters.client_id) && (
            <button
              onClick={handleClearFilters}
              className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <X size={18} />
              Καθαρισμός
            </button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Κατάσταση</label>
                <select
                  value={filters.status || ''}
                  onChange={(e) => handleFilterChange('status', e.target.value as TicketsFilters['status'])}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Προτεραιότητα</label>
                <select
                  value={filters.priority || ''}
                  onChange={(e) => handleFilterChange('priority', e.target.value as TicketsFilters['priority'])}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                >
                  {PRIORITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Πελάτης</label>
                <select
                  value={filters.client_id || ''}
                  onChange={(e) => handleFilterChange('client_id', e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                >
                  <option value="">Όλοι</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.eponimia} ({client.afm})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filters.open_only || false}
                    onChange={(e) => handleFilterChange('open_only', e.target.checked || undefined)}
                    className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-brand-500"
                  />
                  <span className="text-sm text-gray-700">Μόνο ανοιχτά</span>
                </label>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tickets Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-500">Φόρτωση tickets...</span>
          </div>
        ) : isError ? (
          <div className="text-center py-12 text-red-600">
            <p>Σφάλμα φόρτωσης. Δοκιμάστε ξανά.</p>
            <Button variant="secondary" onClick={() => refetch()} className="mt-4">
              Επανάληψη
            </Button>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Τίτλος
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Πελάτης
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Κατάσταση
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Προτεραιότητα
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ημ/νία
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ανάθεση
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ενέργειες
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data?.results?.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                        Δεν βρέθηκαν tickets
                      </td>
                    </tr>
                  ) : (
                    data?.results?.map((ticket) => (
                      <TicketRow
                        key={ticket.id}
                        ticket={ticket}
                        onOpenDetail={() => handleOpenDetail(ticket)}
                        onRefetch={refetch}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200">
                <p className="text-sm text-gray-500">
                  Εμφάνιση {((currentPage - 1) * (filters.page_size || 20)) + 1} -{' '}
                  {Math.min(currentPage * (filters.page_size || 20), data?.count || 0)} από {data?.count || 0}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="p-2 border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span className="text-sm text-gray-700">
                    Σελίδα {currentPage} από {totalPages}
                  </span>
                  <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className="p-2 border border-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Create Ticket Modal */}
      {createModalOpen && (
        <CreateTicketModal
          onClose={() => setCreateModalOpen(false)}
          onSuccess={() => {
            setCreateModalOpen(false);
            refetch();
          }}
          clients={clients}
        />
      )}

      {/* Ticket Detail Modal */}
      {detailModalOpen && selectedTicket && (
        <TicketDetailModal
          ticket={selectedTicket}
          onClose={() => {
            setDetailModalOpen(false);
            setSelectedTicket(null);
          }}
          onRefetch={refetch}
          clients={clients}
        />
      )}
    </div>
  );
}

// ============================================
// TICKET ROW COMPONENT
// ============================================
function TicketRow({
  ticket,
  onOpenDetail,
  onRefetch,
}: {
  ticket: TicketFull;
  onOpenDetail: () => void;
  onRefetch: () => void;
}) {
  const changeStatusMutation = useChangeTicketStatus();

  const handleQuickStatus = async (newStatus: 'in_progress' | 'resolved' | 'closed') => {
    try {
      await changeStatusMutation.mutateAsync({ id: ticket.id, status: newStatus });
      onRefetch();
    } catch (error) {
      console.error('Error changing status:', error);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('el-GR');
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4">
        <div className="max-w-xs">
          <p className="font-medium text-gray-900 truncate">{ticket.title}</p>
          {ticket.call && (
            <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
              <Phone size={12} />
              <span>{ticket.call.phone_number}</span>
            </div>
          )}
        </div>
      </td>
      <td className="px-6 py-4 text-sm">
        {ticket.client ? (
          <Link
            to={`/clients/${ticket.client.id}`}
            className="text-blue-600 hover:underline font-medium"
          >
            {ticket.client.eponimia}
          </Link>
        ) : (
          <span className="text-gray-400 italic">-</span>
        )}
      </td>
      <td className="px-6 py-4">
        <span className={`px-2 py-1 text-xs font-medium rounded ${STATUS_COLORS[ticket.status]}`}>
          {STATUS_LABELS[ticket.status] || ticket.status}
        </span>
      </td>
      <td className="px-6 py-4">
        <span className={`px-2 py-1 text-xs font-medium rounded ${PRIORITY_COLORS[ticket.priority]}`}>
          {PRIORITY_LABELS[ticket.priority] || ticket.priority}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-gray-500">
        {formatDate(ticket.created_at)}
        {ticket.days_since_created > 0 && (
          <span className="text-xs text-gray-400 ml-1">
            ({ticket.days_since_created} μέρες)
          </span>
        )}
      </td>
      <td className="px-6 py-4 text-sm text-gray-500">
        {ticket.assigned_to_name || '-'}
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center gap-2">
          <button
            onClick={onOpenDetail}
            className="p-1.5 text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title="Λεπτομέρειες"
          >
            <Edit size={16} />
          </button>
          {ticket.is_open && (
            <>
              {ticket.status === 'open' && (
                <button
                  onClick={() => handleQuickStatus('in_progress')}
                  className="p-1.5 text-yellow-600 hover:bg-yellow-50 rounded transition-colors"
                  title="Ξεκίνησε"
                >
                  <Clock size={16} />
                </button>
              )}
              {ticket.status === 'in_progress' && (
                <button
                  onClick={() => handleQuickStatus('resolved')}
                  className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                  title="Επίλυση"
                >
                  <Check size={16} />
                </button>
              )}
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

// ============================================
// CREATE TICKET MODAL
// ============================================
function CreateTicketModal({
  onClose,
  onSuccess,
  clients,
}: {
  onClose: () => void;
  onSuccess: () => void;
  clients: Array<{ id: number; eponimia: string; afm: string }>;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium');
  const [clientId, setClientId] = useState<number | null>(null);
  const createMutation = useCreateTicket();

  const handleSubmit = async () => {
    try {
      await createMutation.mutateAsync({
        title,
        description,
        priority,
        client: clientId || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Error creating ticket:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">Νέο Ticket</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Τίτλος *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              placeholder="Σύντομη περιγραφή του θέματος"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Πελάτης
            </label>
            <select
              value={clientId || ''}
              onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg"
            >
              <option value="">-- Χωρίς πελάτη --</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.eponimia} ({client.afm})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Περιγραφή
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg resize-none"
              placeholder="Λεπτομέρειες..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Προτεραιότητα
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as typeof priority)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg"
            >
              <option value="low">Χαμηλή</option>
              <option value="medium">Μεσαία</option>
              <option value="high">Υψηλή</option>
              <option value="urgent">Επείγον</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-3 p-4 border-t bg-gray-50">
          <Button variant="secondary" onClick={onClose}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!title.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-2" />
            )}
            Δημιουργία
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// TICKET DETAIL MODAL
// ============================================
function TicketDetailModal({
  ticket,
  onClose,
  onRefetch,
  clients,
}: {
  ticket: TicketFull;
  onClose: () => void;
  onRefetch: () => void;
  clients: Array<{ id: number; eponimia: string; afm: string }>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(ticket.title);
  const [description, setDescription] = useState(ticket.description || '');
  const [status, setStatus] = useState(ticket.status);
  const [priority, setPriority] = useState(ticket.priority);
  const [notes, setNotes] = useState(ticket.notes || '');
  const [assignedTo, setAssignedTo] = useState<number | null>(ticket.assigned_to || null);
  const [clientId, setClientId] = useState<number | null>(ticket.client?.id || null);

  // Fetch users for assignment dropdown
  const { data: usersData, isLoading: usersLoading } = useUsers();
  const users = usersData?.users || [];

  const updateMutation = useUpdateTicket();
  const changeStatusMutation = useChangeTicketStatus();
  const deleteMutation = useDeleteTicket();

  const handleUpdate = async () => {
    try {
      await updateMutation.mutateAsync({
        id: ticket.id,
        data: { title, description, status, priority, notes, assigned_to: assignedTo, client_id: clientId },
      });
      setIsEditing(false);
      onRefetch();
    } catch (error) {
      console.error('Error updating ticket:', error);
    }
  };

  const handleStatusChange = async (newStatus: 'open' | 'in_progress' | 'resolved' | 'closed') => {
    try {
      await changeStatusMutation.mutateAsync({ id: ticket.id, status: newStatus });
      onRefetch();
    } catch (error) {
      console.error('Error changing status:', error);
    }
  };

  const handleDelete = async () => {
    if (confirm('Διαγραφή αυτού του ticket;')) {
      try {
        await deleteMutation.mutateAsync(ticket.id);
        onClose();
        onRefetch();
      } catch (error) {
        console.error('Error deleting ticket:', error);
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white">
          <h3 className="text-lg font-semibold">Ticket #{ticket.id}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Status and Priority */}
          <div className="flex items-center gap-3">
            <span className={`px-2 py-1 text-xs font-medium rounded ${STATUS_COLORS[ticket.status]}`}>
              {STATUS_LABELS[ticket.status] || ticket.status}
            </span>
            <span className={`px-2 py-1 text-xs font-medium rounded ${PRIORITY_COLORS[ticket.priority]}`}>
              {PRIORITY_LABELS[ticket.priority] || ticket.priority}
            </span>
            <span className="text-sm text-gray-500">
              Δημιουργία: {new Date(ticket.created_at).toLocaleDateString('el-GR')}
            </span>
          </div>

          {/* Client and Call info */}
          {isEditing ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Πελάτης</label>
              <select
                value={clientId || ''}
                onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              >
                <option value="">-- Χωρίς πελάτη --</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.eponimia} ({client.afm})
                  </option>
                ))}
              </select>
              {ticket.call && (
                <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
                  <Phone size={14} className="text-gray-400" />
                  <span className="font-mono">{ticket.call.phone_number}</span>
                  <span>({ticket.call.direction_display})</span>
                </div>
              )}
            </div>
          ) : (ticket.client || ticket.call) ? (
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              {ticket.client && (
                <div className="flex items-center gap-2">
                  <User size={16} className="text-gray-400" />
                  <Link
                    to={`/clients/${ticket.client.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {ticket.client.eponimia}
                  </Link>
                  <span className="text-sm text-gray-500">({ticket.client.afm})</span>
                </div>
              )}
              {ticket.call && (
                <div className="flex items-center gap-2">
                  <Phone size={16} className="text-gray-400" />
                  <span className="font-mono">{ticket.call.phone_number}</span>
                  <span className="text-sm text-gray-500">
                    ({ticket.call.direction_display})
                  </span>
                </div>
              )}
            </div>
          ) : null}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Τίτλος</label>
            {isEditing ? (
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              />
            ) : (
              <p className="text-gray-900">{ticket.title}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Περιγραφή</label>
            {isEditing ? (
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg resize-none"
              />
            ) : (
              <p className="text-gray-600 whitespace-pre-wrap">
                {ticket.description || <span className="italic text-gray-400">Χωρίς περιγραφή</span>}
              </p>
            )}
          </div>

          {/* Status (editable) */}
          {isEditing && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Κατάσταση</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as typeof status)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              >
                <option value="open">Ανοιχτό</option>
                <option value="assigned">Ανατέθηκε</option>
                <option value="in_progress">Σε εξέλιξη</option>
                <option value="resolved">Επιλύθηκε</option>
                <option value="closed">Κλειστό</option>
              </select>
            </div>
          )}

          {/* Priority (editable) */}
          {isEditing && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Προτεραιότητα</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as typeof priority)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              >
                <option value="low">Χαμηλή</option>
                <option value="medium">Μεσαία</option>
                <option value="high">Υψηλή</option>
                <option value="urgent">Επείγον</option>
              </select>
            </div>
          )}

          {/* Assigned To (editable) */}
          {isEditing && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ανάθεση σε</label>
              <select
                value={assignedTo || ''}
                onChange={(e) => setAssignedTo(e.target.value ? Number(e.target.value) : null)}
                disabled={usersLoading}
                className={`w-full px-3 py-2 border border-gray-200 rounded-lg ${
                  usersLoading ? 'bg-gray-100' : ''
                }`}
              >
                <option value="">-- Χωρίς ανάθεση --</option>
                {users.filter(u => u.is_active).map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.first_name && user.last_name
                      ? `${user.first_name} ${user.last_name}`
                      : user.username}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Display assigned_to when not editing */}
          {!isEditing && ticket.assigned_to_name && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ανατεθειμένο σε</label>
              <p className="text-gray-600">{ticket.assigned_to_name}</p>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Σημειώσεις</label>
            {isEditing ? (
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg resize-none"
                placeholder="Εσωτερικές σημειώσεις..."
              />
            ) : (
              <p className="text-gray-600 whitespace-pre-wrap">
                {ticket.notes || <span className="italic text-gray-400">Χωρίς σημειώσεις</span>}
              </p>
            )}
          </div>

          {/* Status Change Buttons */}
          {ticket.is_open && !isEditing && (
            <div className="flex flex-wrap gap-2 pt-4 border-t">
              <p className="w-full text-sm font-medium text-gray-700 mb-2">Αλλαγή κατάστασης:</p>
              {ticket.status !== 'in_progress' && (
                <button
                  onClick={() => handleStatusChange('in_progress')}
                  className="px-3 py-1.5 text-sm bg-yellow-100 text-yellow-800 rounded-lg hover:bg-yellow-200 transition-colors"
                >
                  Σε εξέλιξη
                </button>
              )}
              {ticket.status !== 'resolved' && (
                <button
                  onClick={() => handleStatusChange('resolved')}
                  className="px-3 py-1.5 text-sm bg-green-100 text-green-800 rounded-lg hover:bg-green-200 transition-colors"
                >
                  Επιλύθηκε
                </button>
              )}
              <button
                onClick={() => handleStatusChange('closed')}
                className="px-3 py-1.5 text-sm bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Κλείσιμο
              </button>
            </div>
          )}

          {/* Re-open button for closed tickets */}
          {!ticket.is_open && !isEditing && (
            <div className="flex flex-wrap gap-2 pt-4 border-t">
              <button
                onClick={() => handleStatusChange('open')}
                className="px-3 py-1.5 text-sm bg-blue-100 text-blue-800 rounded-lg hover:bg-blue-200 transition-colors"
              >
                Επαναφορά σε ανοιχτό
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between p-4 border-t bg-gray-50">
          <button
            onClick={handleDelete}
            className="px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            Διαγραφή
          </button>
          <div className="flex gap-2">
            {isEditing ? (
              <>
                <Button variant="secondary" onClick={() => setIsEditing(false)}>
                  Ακύρωση
                </Button>
                <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
                  {updateMutation.isPending && <RefreshCw className="w-4 h-4 mr-2 animate-spin" />}
                  Αποθήκευση
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" onClick={onClose}>
                  Κλείσιμο
                </Button>
                <Button onClick={() => setIsEditing(true)}>
                  <Edit className="w-4 h-4 mr-2" />
                  Επεξεργασία
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
