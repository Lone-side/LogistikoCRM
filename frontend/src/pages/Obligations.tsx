import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useDebounce } from '../hooks/useDebounce';
import {
  useObligations,
  useCreateObligation,
  useDeleteObligation,
  useObligationTypes,
  useBulkCreateObligations,
  useBulkDeleteObligations,
  exportObligationsToExcel,
  useGenerateMonthlyObligations,
  useClientsWithObligationStatus,
  useBulkAssignObligations,
  useObligationTypesGrouped,
  useObligationProfiles,
} from '../hooks/useObligations';
import { useCompleteAndNotify, useBulkCompleteWithDocuments, useSendObligationNotice } from '../hooks/useEmail';
import { useUploadToObligation } from '../hooks/useDocuments';
import type { GenerateMonthResult, Client } from '../types';
import { useClients } from '../hooks/useClients';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import { Modal, ConfirmDialog, ObligationForm, Button, TableSkeleton } from '../components';
import { DocumentUploadModal } from '../components/DocumentUploadModal';
import { SendEmailModal } from '../components/SendEmailModal';
import { CompleteObligationModal } from '../components/CompleteObligationModal';
import { BulkCompleteModal } from '../components/BulkCompleteModal';
import {
  FileText, AlertCircle, RefreshCw, Filter, Plus, Edit2, Trash2,
  Download, CheckSquare, Square, Users, Calendar, CalendarPlus, CheckCircle, X,
  Paperclip, Mail, AlertTriangle, Settings, UserPlus
} from 'lucide-react';
import type { Obligation, ObligationFormData, BulkObligationFormData } from '../types';
import { Badge, EmptyState, PageHeader, type BadgeVariant } from '../components/ui';
import {
  OBLIGATION_STATUS_LABELS,
  MONTHS,
  YEARS,
} from '../constants';

// Alias for backwards compatibility within this file
const STATUS_LABELS = OBLIGATION_STATUS_LABELS;
const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  pending: 'warning',
  in_progress: 'info',
  completed: 'success',
  overdue: 'danger',
  cancelled: 'neutral',
};
const currentYear = new Date().getFullYear();

interface Filters {
  status: string;
  client: number | null;
  type: string;
  month: number | null;
  year: number | null;
  deadline_from: string;
  deadline_to: string;
}

export default function Obligations() {
  const [page, setPage] = useState(1);
  const pageSize = 100;

  // Αρχικό φίλτρο κατάστασης από το URL (π.χ. /obligations?status=overdue από τα tiles του dashboard)
  const initialStatus = new URLSearchParams(window.location.search).get('status');

  // Filters state
  const [filters, setFilters] = useState<Filters>({
    status: initialStatus && initialStatus in STATUS_LABELS ? initialStatus : 'all',
    client: null,
    type: '',
    month: null,
    year: null,
    deadline_from: '',
    deadline_to: '',
  });
  const [showFilters, setShowFilters] = useState(false);

  // Selection state for bulk operations
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectAll, setSelectAll] = useState(false);

  // Modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isBulkCreateModalOpen, setIsBulkCreateModalOpen] = useState(false);
  const [isBulkDeleteDialogOpen, setIsBulkDeleteDialogOpen] = useState(false);
  const [isGenerateMonthModalOpen, setIsGenerateMonthModalOpen] = useState(false);
  const [generateResult, setGenerateResult] = useState<GenerateMonthResult | null>(null);
  const [selectedObligation, setSelectedObligation] = useState<Obligation | null>(null);
  const [isBulkAssignModalOpen, setIsBulkAssignModalOpen] = useState(false);

  // New modal states for complete, upload, email
  const [isCompleteModalOpen, setIsCompleteModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [isBulkCompleteModalOpen, setIsBulkCompleteModalOpen] = useState(false);

  // Bulk create form state
  const [bulkCreateForm, setBulkCreateForm] = useState<BulkObligationFormData>({
    client_ids: [],
    obligation_type: 0,
    month: new Date().getMonth() + 1,
    year: currentYear,
  });

  // Build query params
  const queryParams = useMemo(() => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filters.status !== 'all') params.status = filters.status;
    if (filters.client) params.client = filters.client;
    if (filters.type) params.type = filters.type;
    if (filters.month) params.month = filters.month;
    if (filters.year) params.year = filters.year;
    if (filters.deadline_from) params.deadline_from = filters.deadline_from;
    if (filters.deadline_to) params.deadline_to = filters.deadline_to;
    return params;
  }, [page, pageSize, filters]);

  const { data, isLoading, isError, error, refetch } = useObligations(queryParams);
  const { data: clientsData } = useClients({ page_size: 1000 });
  const { data: obligationTypes } = useObligationTypes();
  const createMutation = useCreateObligation();
  const deleteMutation = useDeleteObligation();
  const bulkCreateMutation = useBulkCreateObligations();
  const bulkDeleteMutation = useBulkDeleteObligations();
  const generateMonthMutation = useGenerateMonthlyObligations();
  const completeAndNotifyMutation = useCompleteAndNotify();
  const bulkCompleteWithDocsMutation = useBulkCompleteWithDocuments();
  const sendObligationNoticeMutation = useSendObligationNotice();
  const uploadToObligationMutation = useUploadToObligation();
  const queryClient = useQueryClient();

  // Update obligation mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<ObligationFormData> }) => {
      const response = await apiClient.patch<Obligation>(`/api/v1/obligations/${id}/`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obligations'] });
    },
  });

  const obligations = data?.results || [];
  const clients = clientsData?.results || [];

  // Format date for display
  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '-';
    return date.toLocaleDateString('el-GR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  // Selection handlers
  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(obligations.map((o) => o.id)));
    }
    setSelectAll(!selectAll);
  };

  const handleSelectOne = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
    setSelectAll(newSelected.size === obligations.length);
  };

  // CRUD handlers
  const handleCreate = (formData: ObligationFormData) => {
    createMutation.mutate(formData, {
      onSuccess: () => {
        setIsCreateModalOpen(false);
        // invalidateQueries in hook triggers automatic refetch
      },
    });
  };

  const handleEdit = (obligation: Obligation) => {
    setSelectedObligation(obligation);
    setIsEditModalOpen(true);
  };

  const handleUpdate = (formData: ObligationFormData) => {
    if (!selectedObligation) return;
    updateMutation.mutate(
      { id: selectedObligation.id, data: formData },
      {
        onSuccess: () => {
          setIsEditModalOpen(false);
          setSelectedObligation(null);
          // invalidateQueries in hook triggers automatic refetch
        },
      }
    );
  };

  const handleDeleteClick = (obligation: Obligation) => {
    setSelectedObligation(obligation);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!selectedObligation) return;
    deleteMutation.mutate(selectedObligation.id, {
      onSuccess: () => {
        setIsDeleteDialogOpen(false);
        setSelectedObligation(null);
        // invalidateQueries in hook triggers automatic refetch
      },
    });
  };

  // Bulk operations handlers
  const handleBulkCreate = () => {
    if (bulkCreateForm.client_ids.length === 0 || !bulkCreateForm.obligation_type) return;

    bulkCreateMutation.mutate(bulkCreateForm, {
      onSuccess: () => {
        setIsBulkCreateModalOpen(false);
        setBulkCreateForm({
          client_ids: [],
          obligation_type: 0,
          month: new Date().getMonth() + 1,
          year: currentYear,
        });
        // invalidateQueries in hook triggers automatic refetch
      },
    });
  };

  const handleBulkDeleteConfirm = () => {
    if (selectedIds.size === 0) return;
    bulkDeleteMutation.mutate(Array.from(selectedIds), {
      onSuccess: () => {
        setIsBulkDeleteDialogOpen(false);
        setSelectedIds(new Set());
        setSelectAll(false);
        // invalidateQueries in hook triggers automatic refetch
      },
    });
  };

  // New handlers for complete, upload, email
  const handleCompleteClick = (obligation: Obligation) => {
    setSelectedObligation(obligation);
    setIsCompleteModalOpen(true);
  };

  const handleUploadClick = (obligation: Obligation) => {
    setSelectedObligation(obligation);
    setIsUploadModalOpen(true);
  };

  const handleEmailClick = (obligation: Obligation) => {
    setSelectedObligation(obligation);
    setIsEmailModalOpen(true);
  };

  const handleCompleteAndNotify = async (data: {
    file?: File | null;
    documentId?: number | null;
    sendEmail: boolean;
    emailTemplateId?: number | null;
    notes: string;
    timeSpent?: number | null;
  }) => {
    if (!selectedObligation) return;
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
    setIsCompleteModalOpen(false);
    setSelectedObligation(null);
    // invalidateQueries in hook triggers automatic refetch
  };

  const handleUploadDocument = async (data: {
    file: File;
    category: string;
    description: string;
    sendEmail: boolean;
  }) => {
    if (!selectedObligation) return;
    await uploadToObligationMutation.mutateAsync({
      obligationId: selectedObligation.id,
      file: data.file,
      description: data.description,
    });
    if (data.sendEmail) {
      await sendObligationNoticeMutation.mutateAsync({
        obligation_id: selectedObligation.id,
        template_type: 'completion',
        include_attachment: true,
      });
    }
    setIsUploadModalOpen(false);
    setSelectedObligation(null);
    // invalidateQueries in hook triggers automatic refetch
  };

  const handleSendEmail = async (data: {
    subject: string;
    body: string;
    templateId?: number;
    attachmentIds: number[];
  }) => {
    if (!selectedObligation) return;
    const client = clients.find((c) => c.id === selectedObligation.client);
    if (!client?.email) return;

    await sendObligationNoticeMutation.mutateAsync({
      obligation_id: selectedObligation.id,
      template_type: 'completion',
      template_id: data.templateId,
      attachment_ids: data.attachmentIds,
    });
    setIsEmailModalOpen(false);
    setSelectedObligation(null);
  };

  // Handler for bulk complete with documents modal
  const handleBulkCompleteWithDocs = async (data: {
    obligationIds: number[];
    obligationFiles: { [key: number]: File | null };
    saveToClientFolders: boolean;
    sendEmails: boolean;
    attachToEmails: boolean;
    templateId?: number | null;
  }) => {
    if (data.obligationIds.length === 0) return;
    await bulkCompleteWithDocsMutation.mutateAsync(data);
    setIsBulkCompleteModalOpen(false);
    setSelectedIds(new Set());
    setSelectAll(false);
    // invalidateQueries in hook triggers automatic refetch
  };

  // Helper to get client for selected obligation
  const getSelectedClient = (): Client | undefined => {
    if (!selectedObligation) return undefined;
    return clients.find((c) => c.id === selectedObligation.client);
  };

  // Helper to get selected obligations for bulk complete modal
  const getSelectedObligations = (): Obligation[] => {
    return obligations.filter((o) => selectedIds.has(o.id));
  };

  // Export handler
  const [isExporting, setIsExporting] = useState(false);
  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportObligationsToExcel(queryParams);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  // Filter handlers
  const handleFilterChange = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
    setSelectedIds(new Set());
    setSelectAll(false);
  };

  const resetFilters = () => {
    setFilters({
      status: 'all',
      client: null,
      type: '',
      month: null,
      year: null,
      deadline_from: '',
      deadline_to: '',
    });
    setPage(1);
  };

  // Bulk create client selection
  const toggleClientSelection = (clientId: number) => {
    const newIds = [...bulkCreateForm.client_ids];
    const idx = newIds.indexOf(clientId);
    if (idx > -1) {
      newIds.splice(idx, 1);
    } else {
      newIds.push(clientId);
    }
    setBulkCreateForm((prev) => ({ ...prev, client_ids: newIds }));
  };

  const selectAllClients = () => {
    const allIds = clients.map((c) => c.id);
    setBulkCreateForm((prev) => ({ ...prev, client_ids: allIds }));
  };

  const deselectAllClients = () => {
    setBulkCreateForm((prev) => ({ ...prev, client_ids: [] }));
  };

  const hasMore = data?.next !== null;
  const totalCount = data?.count || 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <span className="p-2 bg-brand-50 rounded-lg">
              <FileText className="w-6 h-6 text-brand-600" />
            </span>
            Υποχρεώσεις
          </span>
        }
        subtitle={`${totalCount} συνολικά`}
        className="mb-0"
        actions={
          <>
          <Link to="/settings/obligations">
            <Button variant="secondary" title="Ρυθμίσεις τύπων υποχρεώσεων">
              <Settings className="w-4 h-4 mr-2" />
              Ρυθμίσεις
            </Button>
          </Link>
          <Button variant="secondary" onClick={() => setIsGenerateMonthModalOpen(true)}>
            <CalendarPlus className="w-4 h-4 mr-2" />
            Δημιουργία Μήνα
          </Button>
          <Button variant="secondary" onClick={() => setIsBulkAssignModalOpen(true)}>
            <UserPlus className="w-4 h-4 mr-2" />
            Ανάθεση Υποχρεώσεων
          </Button>
          <Button variant="secondary" onClick={() => setIsBulkCreateModalOpen(true)}>
            <Users className="w-4 h-4 mr-2" />
            Μαζική Δημιουργία
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Νέα Υποχρέωση
          </Button>
          </>
        }
      />

      {/* Filter Controls */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          {/* Quick filters row */}
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <div className="flex items-center text-slate-600">
                <Filter className="w-5 h-5 mr-2" />
                <span className="font-medium">Κατάσταση:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: 'all', label: 'Όλες', className: 'bg-slate-800 text-white' },
                  { value: 'pending', label: 'Εκκρεμείς', className: 'bg-warning-600 text-white' },
                  { value: 'completed', label: 'Ολοκληρωμένες', className: 'bg-success-600 text-white' },
                  { value: 'overdue', label: 'Εκπρόθεσμες', className: 'bg-danger-600 text-white' },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => handleFilterChange('status', opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-150 ${
                      filters.status === opt.value
                        ? opt.className
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => setShowFilters(!showFilters)}
                size="sm"
              >
                <Filter className="w-4 h-4 mr-1" />
                {showFilters ? 'Απόκρυψη' : 'Περισσότερα'}
              </Button>
              <Button variant="secondary" onClick={handleExport} isLoading={isExporting} size="sm">
                <Download className="w-4 h-4 mr-1" />
                Εξαγωγή Excel
              </Button>
            </div>
          </div>

          {/* Extended filters */}
          {showFilters && (
            <div className="border-t border-slate-200 pt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Client filter */}
              <div>
                <label htmlFor="obligations-pelatis" className="block text-sm font-medium text-slate-700 mb-1">Πελάτης</label>
                <select
                  id="obligations-pelatis"
                  value={filters.client || ''}
                  onChange={(e) => handleFilterChange('client', e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                >
                  <option value="">Όλοι</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.eponimia}
                    </option>
                  ))}
                </select>
              </div>

              {/* Type filter */}
              <div>
                <label htmlFor="obligations-typos" className="block text-sm font-medium text-slate-700 mb-1">Τύπος</label>
                <select
                  id="obligations-typos"
                  value={filters.type}
                  onChange={(e) => handleFilterChange('type', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                >
                  <option value="">Όλοι</option>
                  {obligationTypes?.map((type) => (
                    <option key={type.id} value={type.code}>
                      {type.code} - {type.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Month filter */}
              <div>
                <label htmlFor="obligations-minas-3" className="block text-sm font-medium text-slate-700 mb-1">Μήνας</label>
                <select
                  id="obligations-minas-3"
                  value={filters.month || ''}
                  onChange={(e) => handleFilterChange('month', e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                >
                  <option value="">Όλοι</option>
                  {MONTHS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Year filter */}
              <div>
                <label htmlFor="obligations-etos-3" className="block text-sm font-medium text-slate-700 mb-1">Έτος</label>
                <select
                  id="obligations-etos-3"
                  value={filters.year || ''}
                  onChange={(e) => handleFilterChange('year', e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                >
                  <option value="">Όλα</option>
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </div>

              {/* Deadline from */}
              <div>
                <label htmlFor="obligations-prothesmia-apo" className="block text-sm font-medium text-slate-700 mb-1">Προθεσμία από</label>
                <input
                  id="obligations-prothesmia-apo"
                  type="date"
                  value={filters.deadline_from}
                  onChange={(e) => handleFilterChange('deadline_from', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                />
              </div>

              {/* Deadline to */}
              <div>
                <label htmlFor="obligations-prothesmia-eos" className="block text-sm font-medium text-slate-700 mb-1">Προθεσμία έως</label>
                <input
                  id="obligations-prothesmia-eos"
                  type="date"
                  value={filters.deadline_to}
                  onChange={(e) => handleFilterChange('deadline_to', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                />
              </div>

              {/* Reset filters */}
              <div className="flex items-end col-span-2 md:col-span-2">
                <Button variant="secondary" onClick={resetFilters} size="sm">
                  Καθαρισμός Φίλτρων
                </Button>
              </div>
            </div>
          )}
        </div>

      {/* Bulk Actions Bar */}
      {selectedIds.size > 0 && (
        <div className="bg-brand-50 border border-brand-200 rounded-lg p-4 flex items-center justify-between">
            <span className="text-brand-800 font-medium">
              {selectedIds.size} επιλεγμένα
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsBulkCompleteModalOpen(true)}
                isLoading={bulkCompleteWithDocsMutation.isPending}
              >
                <CheckSquare className="w-4 h-4 mr-1" />
                Ολοκλήρωση
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => setIsBulkDeleteDialogOpen(true)}
              >
                <Trash2 className="w-4 h-4 mr-1" />
                Διαγραφή
              </Button>
            <button
              onClick={() => {
                setSelectedIds(new Set());
                setSelectAll(false);
              }}
              className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded"
              title="Ακύρωση επιλογής"
              aria-label="Ακύρωση επιλογής"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {isError && (
        <div className="bg-danger-50 border border-danger-100 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AlertCircle className="w-5 h-5 text-danger-600 mr-2" />
              <span className="text-danger-700">
                Σφάλμα φόρτωσης: {error instanceof Error ? error.message : 'Άγνωστο σφάλμα'}
              </span>
            </div>
            <Button variant="secondary" size="sm" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-1" />
              Επανάληψη
            </Button>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <TableSkeleton rows={8} columns={7} showCheckbox />
      )}

      {/* Obligations Table */}
      {!isLoading && !isError && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <p className="text-sm text-slate-500">
                {obligations.length} από {totalCount} υποχρεώσεις
              </p>
            </div>

            {obligations.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Δεν βρέθηκαν υποχρεώσεις με τα επιλεγμένα φίλτρα."
              />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={handleSelectAll}
                            aria-label="Επιλογή όλων"
                            aria-pressed={selectAll}
                            className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150"
                          >
                            {selectAll ? (
                              <CheckSquare className="w-5 h-5" />
                            ) : (
                              <Square className="w-5 h-5" />
                            )}
                          </button>
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Πελάτης
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Τύπος
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Περίοδος
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Προθεσμία
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Κατάσταση
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Ανάθεση
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Έγγραφα
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wide">
                          Ενέργειες
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-slate-100">
                      {obligations.map((obligation) => (
                        <tr key={obligation.id} className={`transition-colors duration-150 hover:bg-slate-50 ${selectedIds.has(obligation.id) ? 'bg-brand-50' : ''}`}>
                          <td className="px-4 py-4">
                            <button
                              onClick={() => handleSelectOne(obligation.id)}
                              aria-label={`Επιλογή υποχρέωσης ${obligation.client_name || obligation.client}`}
                              aria-pressed={selectedIds.has(obligation.id)}
                              className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150"
                            >
                              {selectedIds.has(obligation.id) ? (
                                <CheckSquare className="w-5 h-5 text-brand-600" />
                              ) : (
                                <Square className="w-5 h-5" />
                              )}
                            </button>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-slate-900">
                              {obligation.client_name || `Πελάτης #${obligation.client}`}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="inline-flex px-2 py-1 text-sm font-medium bg-slate-100 text-slate-800 rounded">
                              {obligation.type_name || obligation.type_code || obligation.obligation_type}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">
                            {String(obligation.month).padStart(2, '0')}/{obligation.year}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">
                            {formatDate(obligation.deadline)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <Badge variant={STATUS_VARIANTS[obligation.status] ?? 'neutral'}>
                              {STATUS_LABELS[obligation.status]}
                            </Badge>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                            {obligation.assigned_to_name || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            {(obligation.documents_count ?? 0) > 0 ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-brand-50 text-brand-700 text-xs font-medium">
                                <Paperclip className="w-3 h-3" />
                                {obligation.documents_count}
                              </span>
                            ) : (
                              <span className="text-slate-300 text-sm">-</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div className="flex items-center justify-end gap-1">
                              {/* Complete button - only show for non-completed */}
                              {obligation.status !== 'completed' && (
                                <button
                                  onClick={() => handleCompleteClick(obligation)}
                                  className="text-success-600 hover:text-success-700 p-1.5 hover:bg-success-50 rounded-lg cursor-pointer transition-colors duration-150"
                                  title="Ολοκλήρωση"
                                  aria-label="Ολοκλήρωση"
                                >
                                  <CheckCircle className="w-4 h-4" />
                                </button>
                              )}
                              {/* Attach document button */}
                              <button
                                onClick={() => handleUploadClick(obligation)}
                                className="text-purple-600 hover:text-purple-900 p-1.5 hover:bg-purple-50 rounded-lg cursor-pointer transition-colors duration-150"
                                title="Επισύναψη εγγράφου"
                                aria-label="Επισύναψη εγγράφου"
                              >
                                <Paperclip className="w-4 h-4" />
                              </button>
                              {/* Send email button */}
                              <button
                                onClick={() => handleEmailClick(obligation)}
                                className="text-brand-600 hover:text-brand-900 p-1.5 hover:bg-brand-50 rounded-lg cursor-pointer transition-colors duration-150"
                                title="Αποστολή email"
                                aria-label="Αποστολή email"
                              >
                                <Mail className="w-4 h-4" />
                              </button>
                              {/* Edit button */}
                              <button
                                onClick={() => handleEdit(obligation)}
                                className="text-slate-600 hover:text-slate-900 p-1.5 hover:bg-slate-100 rounded-lg cursor-pointer transition-colors duration-150"
                                title="Επεξεργασία"
                                aria-label="Επεξεργασία"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              {/* Delete button */}
                              <button
                                onClick={() => handleDeleteClick(obligation)}
                                className="text-danger-600 hover:text-danger-700 p-1.5 hover:bg-danger-50 rounded-lg cursor-pointer transition-colors duration-150"
                                title="Διαγραφή"
                                aria-label="Διαγραφή"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Load More / Pagination */}
                {hasMore && (
                  <div className="px-6 py-4 border-t border-slate-200 text-center">
                    <Button variant="secondary" onClick={() => setPage((p) => p + 1)}>
                      Φόρτωση περισσότερων ({obligations.length} από {totalCount})
                    </Button>
                  </div>
                )}
            </>
          )}
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Νέα Υποχρέωση"
        aria-label="Νέα Υποχρέωση"
        size="lg"
      >
        <ObligationForm
          clients={clients}
          onSubmit={handleCreate}
          onCancel={() => setIsCreateModalOpen(false)}
          isLoading={createMutation.isPending}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setSelectedObligation(null);
        }}
        title="Επεξεργασία Υποχρέωσης"
        aria-label="Επεξεργασία Υποχρέωσης"
        size="lg"
      >
        <ObligationForm
          obligation={selectedObligation}
          clients={clients}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditModalOpen(false);
            setSelectedObligation(null);
          }}
          isLoading={updateMutation.isPending}
        />
      </Modal>

      {/* Bulk Create Modal */}
      <Modal
        isOpen={isBulkCreateModalOpen}
        onClose={() => setIsBulkCreateModalOpen(false)}
        title="Μαζική Δημιουργία Υποχρεώσεων"
        aria-label="Μαζική Δημιουργία Υποχρεώσεων"
        size="xl"
      >
        <div className="space-y-4">
          {/* Obligation Type */}
          <div>
            <label htmlFor="obligations-f1" className="block text-sm font-medium text-slate-700 mb-1">
              Τύπος Υποχρέωσης *
            </label>
            <select id="obligations-f1"
              value={bulkCreateForm.obligation_type}
              onChange={(e) =>
                setBulkCreateForm((prev) => ({ ...prev, obligation_type: Number(e.target.value) }))
              }
              className="w-full px-3 py-2 border border-slate-300 rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            >
              <option value={0}>-- Επιλέξτε τύπο --</option>
              {obligationTypes?.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.code} - {type.name}
                </option>
              ))}
            </select>
          </div>

          {/* Period */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="obligations-minas-2" className="block text-sm font-medium text-slate-700 mb-1">Μήνας</label>
              <select
                id="obligations-minas-2"
                value={bulkCreateForm.month}
                onChange={(e) =>
                  setBulkCreateForm((prev) => ({ ...prev, month: Number(e.target.value) }))
                }
                className="w-full px-3 py-2 border border-slate-300 rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              >
                {MONTHS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="obligations-etos-2" className="block text-sm font-medium text-slate-700 mb-1">Έτος</label>
              <select
                id="obligations-etos-2"
                value={bulkCreateForm.year}
                onChange={(e) =>
                  setBulkCreateForm((prev) => ({ ...prev, year: Number(e.target.value) }))
                }
                className="w-full px-3 py-2 border border-slate-300 rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              >
                {YEARS.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Client Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-700">
                Πελάτες ({bulkCreateForm.client_ids.length} επιλεγμένοι) *
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={selectAllClients}
                  className="text-xs text-brand-600 hover:text-brand-800"
                >
                  Επιλογή όλων
                </button>
                <button
                  type="button"
                  onClick={deselectAllClients}
                  className="text-xs text-slate-600 hover:text-slate-800"
                >
                  Αποεπιλογή όλων
                </button>
              </div>
            </div>
            <div className="border border-slate-300 rounded-md max-h-60 overflow-y-auto">
              {clients.map((client) => (
                <label
                  key={client.id}
                  className="flex items-center px-3 py-2 hover:bg-slate-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={bulkCreateForm.client_ids.includes(client.id)}
                    onChange={() => toggleClientSelection(client.id)}
                    className="mr-3"
                  />
                  <span className="text-sm">
                    {client.eponimia} ({client.afm})
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-4 border-t border-slate-200">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsBulkCreateModalOpen(false)}
            >
              Ακύρωση
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleBulkCreate}
              isLoading={bulkCreateMutation.isPending}
              disabled={bulkCreateForm.client_ids.length === 0 || !bulkCreateForm.obligation_type}
            >
              <Calendar className="w-4 h-4 mr-2" />
              Δημιουργία για {bulkCreateForm.client_ids.length} πελάτες
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSelectedObligation(null);
        }}
        onConfirm={handleDeleteConfirm}
        title="Διαγραφή Υποχρέωσης"
        aria-label="Διαγραφή Υποχρέωσης"
        message={`Είστε σίγουροι ότι θέλετε να διαγράψετε την υποχρέωση για ${selectedObligation?.client_name || 'τον πελάτη'};`}
        confirmText="Διαγραφή"
        cancelText="Ακύρωση"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />

      {/* Bulk Delete Confirmation */}
      <ConfirmDialog
        isOpen={isBulkDeleteDialogOpen}
        onClose={() => setIsBulkDeleteDialogOpen(false)}
        onConfirm={handleBulkDeleteConfirm}
        title="Διαγραφή Επιλεγμένων Υποχρεώσεων"
        aria-label="Διαγραφή Επιλεγμένων Υποχρεώσεων"
        message={
          selectAll
            ? `Πρόκειται να διαγράψεις ΟΛΕΣ τις ${selectedIds.size} υποχρεώσεις που εμφανίζονται αυτή τη στιγμή στη λίστα. Η ενέργεια δεν αναιρείται.`
            : `Είστε σίγουροι ότι θέλετε να διαγράψετε ${selectedIds.size} υποχρεώσεις; Η ενέργεια δεν αναιρείται.`
        }
        confirmText="Διαγραφή"
        cancelText="Ακύρωση"
        isLoading={bulkDeleteMutation.isPending}
        variant="danger"
        requireTypedConfirmation={String(selectedIds.size)}
        typedConfirmationLabel={`Πληκτρολόγησε τον αριθμό ${selectedIds.size} για επιβεβαίωση`}
      />

      {/* Generate Month Modal */}
      <GenerateMonthModal
        isOpen={isGenerateMonthModalOpen}
        onClose={() => {
          setIsGenerateMonthModalOpen(false);
          setGenerateResult(null);
        }}
        onGenerate={async (data) => {
          const result = await generateMonthMutation.mutateAsync(data);
          setGenerateResult(result);
          // invalidateQueries in hook triggers automatic refetch
        }}
        isLoading={generateMonthMutation.isPending}
        result={generateResult}
        onOpenBulkAssign={() => setIsBulkAssignModalOpen(true)}
      />

      {/* Complete Obligation Modal */}
      <CompleteObligationModal
        isOpen={isCompleteModalOpen}
        onClose={() => {
          setIsCompleteModalOpen(false);
          setSelectedObligation(null);
        }}
        obligation={selectedObligation}
        clientName={getSelectedClient()?.eponimia || ''}
        clientEmail={getSelectedClient()?.email || undefined}
        onComplete={handleCompleteAndNotify}
        isLoading={completeAndNotifyMutation.isPending}
      />

      {/* Document Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => {
          setIsUploadModalOpen(false);
          setSelectedObligation(null);
        }}
        onUpload={handleUploadDocument}
        clientName={getSelectedClient()?.eponimia}
        obligationType={selectedObligation?.type_name || selectedObligation?.type_code}
        isLoading={uploadToObligationMutation.isPending}
      />

      {/* Send Email Modal */}
      <SendEmailModal
        isOpen={isEmailModalOpen}
        onClose={() => {
          setIsEmailModalOpen(false);
          setSelectedObligation(null);
        }}
        onSend={handleSendEmail}
        clientName={getSelectedClient()?.eponimia || ''}
        clientEmail={getSelectedClient()?.email || ''}
        obligationId={selectedObligation?.id}
        isLoading={sendObligationNoticeMutation.isPending}
      />

      {/* Bulk Complete Modal with Documents */}
      <BulkCompleteModal
        isOpen={isBulkCompleteModalOpen}
        onClose={() => setIsBulkCompleteModalOpen(false)}
        obligations={getSelectedObligations()}
        onComplete={handleBulkCompleteWithDocs}
        isLoading={bulkCompleteWithDocsMutation.isPending}
      />

      {/* Bulk Assign Obligations Modal */}
      <BulkAssignModal
        isOpen={isBulkAssignModalOpen}
        onClose={() => setIsBulkAssignModalOpen(false)}
        onSuccess={() => {
          // Refresh data after successful bulk assign
          refetch();
        }}
      />
    </div>
  );
}

// ============================================
// GENERATE MONTH MODAL COMPONENT
// ============================================
interface GenerateMonthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (data: { month: number; year: number; client_ids?: number[] }) => Promise<void>;
  isLoading: boolean;
  result: GenerateMonthResult | null;
  onOpenBulkAssign: () => void;
}

function GenerateMonthModal({
  isOpen,
  onClose,
  onGenerate,
  isLoading,
  result,
  onOpenBulkAssign,
}: GenerateMonthModalProps) {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [month, setMonth] = useState(currentMonth);
  const [year, setYear] = useState(currentYear);
  const [useAllClients, setUseAllClients] = useState(true);
  const [selectedClientIds, setSelectedClientIds] = useState<number[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showOnlyWithProfiles, setShowOnlyWithProfiles] = useState(true);
  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  // Fetch clients with their obligation status
  const { data: clientsWithStatus, isLoading: isLoadingClients } = useClientsWithObligationStatus();

  // Calculate statistics
  const stats = useMemo(() => {
    if (!clientsWithStatus) return { total: 0, withProfile: 0, withoutProfile: 0 };
    const withProfile = clientsWithStatus.filter(c => c.has_obligation_profile).length;
    return {
      total: clientsWithStatus.length,
      withProfile,
      withoutProfile: clientsWithStatus.length - withProfile
    };
  }, [clientsWithStatus]);

  // Filter clients by search and profile status
  const filteredClients = useMemo(() => {
    if (!clientsWithStatus) return [];
    return clientsWithStatus.filter((c) => {
      const matchesSearch = c.eponimia.toLowerCase().includes(debouncedSearchTerm.toLowerCase()) ||
                           c.afm.includes(debouncedSearchTerm);
      const matchesProfileFilter = !showOnlyWithProfiles || c.has_obligation_profile;
      return matchesSearch && matchesProfileFilter;
    });
  }, [clientsWithStatus, debouncedSearchTerm, showOnlyWithProfiles]);

  // Clients with profiles for selection
  const clientsWithProfiles = useMemo(() => {
    return filteredClients.filter(c => c.has_obligation_profile);
  }, [filteredClients]);

  // Toggle client selection
  const toggleClient = (clientId: number) => {
    if (selectedClientIds.includes(clientId)) {
      setSelectedClientIds(selectedClientIds.filter((id) => id !== clientId));
    } else {
      setSelectedClientIds([...selectedClientIds, clientId]);
    }
  };

  // Select all filtered clients WITH profiles
  const selectAll = () => {
    setSelectedClientIds(clientsWithProfiles.map((c) => c.id));
  };

  // Deselect all
  const deselectAll = () => {
    setSelectedClientIds([]);
  };

  // Handle submit
  const handleSubmit = async () => {
    await onGenerate({
      month,
      year,
      client_ids: useAllClients ? undefined : selectedClientIds,
    });
  };

  // Reset form when modal closes
  const handleClose = () => {
    setMonth(currentMonth);
    setYear(currentYear);
    setUseAllClients(true);
    setSelectedClientIds([]);
    setSearchTerm('');
    onClose();
  };

  if (!isOpen) return null;

  // Show result view if we have a result
  if (result) {
    const hasClientsWithoutProfile = result.details?.some(d => d.note?.includes('προφίλ'));
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div role="dialog" aria-modal="true" className="bg-white rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center">
              <CheckCircle className="w-6 h-6 text-success-600 mr-2" />
              <h2 className="text-lg font-semibold text-slate-900">Ολοκληρώθηκε</h2>
            </div>
            <button aria-label="Κλείσιμο" onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-lg">
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>
          <div className="p-6 space-y-4 overflow-y-auto">
            {/* Summary */}
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-success-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-success-700">{result.created_count}</p>
                <p className="text-sm text-success-600">Δημιουργήθηκαν</p>
              </div>
              <div className="bg-warning-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-warning-700">{result.skipped_count}</p>
                <p className="text-sm text-warning-600">Παραλείφθηκαν</p>
              </div>
              <div className="bg-brand-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-brand-700">{result.clients_processed}</p>
                <p className="text-sm text-brand-600">Πελάτες</p>
              </div>
            </div>

            {/* Warning for clients without profiles */}
            {hasClientsWithoutProfile && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">
                      Κάποιοι πελάτες δεν έχουν ρυθμισμένο προφίλ υποχρεώσεων
                    </p>
                    <p className="text-sm text-amber-700 mt-1">
                      Για αυτούς τους πελάτες δεν δημιουργήθηκαν υποχρεώσεις.
                      Χρησιμοποιήστε τη "Μαζική Ανάθεση" για να τους ρυθμίσετε.
                    </p>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => { handleClose(); onOpenBulkAssign(); }}
                      className="mt-2"
                    >
                      <UserPlus className="w-4 h-4 mr-1" />
                      Μαζική Ανάθεση Υποχρεώσεων
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Details */}
            {result.details && result.details.length > 0 && (
              <div>
                <h3 className="font-medium text-slate-900 mb-2">Λεπτομέρειες</h3>
                <div className="border rounded-lg max-h-60 overflow-y-auto divide-y">
                  {result.details.map((detail) => (
                    <div key={detail.client_id} className="p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-slate-900">{detail.client_name}</p>
                        {detail.note && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            Χωρίς προφίλ
                          </span>
                        )}
                      </div>
                      {detail.created.length > 0 && (
                        <p className="text-success-600 text-xs mt-1">
                          Δημιουργήθηκαν: {detail.created.join(', ')}
                        </p>
                      )}
                      {detail.skipped.length > 0 && (
                        <p className="text-warning-600 text-xs mt-1">
                          Παραλείφθηκαν: {detail.skipped.join(', ')}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="p-4 border-t bg-slate-50">
            <Button onClick={handleClose} className="w-full">
              Κλείσιμο
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div role="dialog" aria-modal="true" className="bg-white rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center">
            <CalendarPlus className="w-6 h-6 text-warning-600 mr-2" />
            <h2 className="text-lg font-semibold text-slate-900">Δημιουργία Υποχρεώσεων Μήνα</h2>
          </div>
          <button aria-label="Κλείσιμο" onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-lg" disabled={isLoading}>
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>
        <div className="p-4 space-y-4 overflow-y-auto">
          {/* Statistics Cards */}
          {!isLoadingClients && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-50 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-slate-700">{stats.total}</p>
                <p className="text-xs text-slate-500">Ενεργοί πελάτες</p>
              </div>
              <div className="bg-success-50 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-success-700">{stats.withProfile}</p>
                <p className="text-xs text-success-600">Με υποχρεώσεις</p>
              </div>
              <div className={`rounded-lg p-3 text-center ${stats.withoutProfile > 0 ? 'bg-amber-50' : 'bg-slate-50'}`}>
                <p className={`text-xl font-bold ${stats.withoutProfile > 0 ? 'text-amber-700' : 'text-slate-700'}`}>
                  {stats.withoutProfile}
                </p>
                <p className={`text-xs ${stats.withoutProfile > 0 ? 'text-amber-600' : 'text-slate-500'}`}>
                  Χωρίς υποχρεώσεις
                </p>
              </div>
            </div>
          )}

          {/* Warning Banner */}
          {stats.withoutProfile > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-amber-800">
                    {stats.withoutProfile} πελάτες χωρίς ρυθμισμένες υποχρεώσεις
                  </p>
                  <p className="text-sm text-amber-700 mt-1">
                    Για αυτούς τους πελάτες ΔΕΝ θα δημιουργηθούν υποχρεώσεις.
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { handleClose(); onOpenBulkAssign(); }}
                    className="mt-2"
                  >
                    <UserPlus className="w-4 h-4 mr-1" />
                    Μαζική Ανάθεση Υποχρεώσεων
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Period Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="obligations-minas" className="block text-sm font-medium text-slate-700 mb-1">Μήνας</label>
              <select
                id="obligations-minas"
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                disabled={isLoading}
              >
                {MONTHS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="obligations-etos" className="block text-sm font-medium text-slate-700 mb-1">Έτος</label>
              <select
                id="obligations-etos"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                disabled={isLoading}
              >
                {YEARS.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Client Selection Mode */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Πελάτες</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={useAllClients}
                  onChange={() => setUseAllClients(true)}
                  className="h-4 w-4 text-brand-600"
                  disabled={isLoading}
                />
                <span className="text-sm text-slate-700">
                  Όλοι οι πελάτες με ρυθμισμένες υποχρεώσεις ({stats.withProfile})
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={!useAllClients}
                  onChange={() => setUseAllClients(false)}
                  className="h-4 w-4 text-brand-600"
                  disabled={isLoading}
                />
                <span className="text-sm text-slate-700">Επιλεγμένοι πελάτες</span>
              </label>
            </div>
          </div>

          {/* Client List (if not all) */}
          {!useAllClients && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-slate-700">
                  Επιλέξτε πελάτες ({selectedClientIds.length} επιλεγμένοι)
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={selectAll}
                    className="text-xs text-brand-600 hover:text-brand-800"
                    disabled={isLoading}
                  >
                    Επιλογή όλων
                  </button>
                  <button
                    type="button"
                    onClick={deselectAll}
                    className="text-xs text-slate-600 hover:text-slate-800"
                    disabled={isLoading}
                  >
                    Αποεπιλογή όλων
                  </button>
                </div>
              </div>

              {/* Search and Filter */}
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="Αναζήτηση πελάτη..."
                  aria-label="Αναζήτηση πελάτη"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  disabled={isLoading}
                />
                <label className="flex items-center gap-1.5 px-3 py-2 bg-slate-50 border border-slate-300 rounded-md cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showOnlyWithProfiles}
                    onChange={(e) => setShowOnlyWithProfiles(e.target.checked)}
                    className="h-4 w-4 text-brand-600 rounded"
                    disabled={isLoading}
                  />
                  <span className="text-xs text-slate-600 whitespace-nowrap">Μόνο με προφίλ</span>
                </label>
              </div>

              {/* Client List */}
              <div className="border border-slate-300 rounded-md max-h-48 overflow-y-auto">
                {isLoadingClients ? (
                  <div className="p-4 text-center text-slate-500 text-sm">
                    Φόρτωση πελατών...
                  </div>
                ) : filteredClients.length === 0 ? (
                  <div className="p-4 text-center text-slate-500 text-sm">
                    Δεν βρέθηκαν πελάτες
                  </div>
                ) : (
                  filteredClients.map((client) => (
                    <label
                      key={client.id}
                      className={`flex items-center px-3 py-2 hover:bg-slate-50 cursor-pointer ${
                        !client.has_obligation_profile ? 'bg-amber-50/50' : ''
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedClientIds.includes(client.id)}
                        onChange={() => toggleClient(client.id)}
                        className="mr-3 h-4 w-4 text-brand-600 rounded"
                        disabled={isLoading || !client.has_obligation_profile}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm truncate">
                            {client.eponimia}
                          </span>
                          {client.has_obligation_profile ? (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-success-100 text-success-700">
                              {client.obligation_types_count} υποχρ.
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                              <AlertTriangle className="w-3 h-3 mr-0.5" />
                              Χωρίς προφίλ
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500">
                          <span>{client.afm}</span>
                          {client.obligation_profile_names.length > 0 && (
                            <span> • {client.obligation_profile_names.join(', ')}</span>
                          )}
                          {client.groups_used && client.groups_used.length > 0 && (
                            <span className="text-brand-600"> • Ομάδες: {client.groups_used.join(', ')}</span>
                          )}
                        </div>
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Info */}
          <div className="bg-brand-50 border border-brand-200 rounded-lg p-3">
            <p className="text-sm text-brand-700">
              Θα δημιουργηθούν υποχρεώσεις βάσει του προφίλ κάθε πελάτη.
              Υποχρεώσεις που υπάρχουν ήδη θα παραλειφθούν.
            </p>
          </div>
        </div>
        <div className="flex gap-3 p-4 border-t bg-slate-50">
          <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleSubmit}
            isLoading={isLoading}
            disabled={isLoading || (!useAllClients && selectedClientIds.length === 0) || stats.withProfile === 0}
            className="flex-1"
          >
            <CalendarPlus className="w-4 h-4 mr-2" />
            Δημιουργία για {useAllClients ? stats.withProfile : selectedClientIds.length} πελάτες
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// BULK ASSIGN MODAL COMPONENT
// ============================================
interface BulkAssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

function BulkAssignModal({ isOpen, onClose, onSuccess }: BulkAssignModalProps) {
  const [selectedClientIds, setSelectedClientIds] = useState<number[]>([]);
  const [selectedTypeIds, setSelectedTypeIds] = useState<number[]>([]);
  const [selectedProfileIds, setSelectedProfileIds] = useState<number[]>([]);
  const [assignMode, setAssignMode] = useState<'add' | 'replace'>('add');
  const [generateCurrentMonth, setGenerateCurrentMonth] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showOnlyWithoutProfiles, setShowOnlyWithoutProfiles] = useState(true);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    created_count: number;
    updated_count: number;
    clients_processed: number;
  } | null>(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  // Fetch data
  const { data: clientsWithStatus, isLoading: isLoadingClients } = useClientsWithObligationStatus();
  const { data: typesGrouped, isLoading: isLoadingTypes } = useObligationTypesGrouped();
  const { data: profiles, isLoading: isLoadingProfiles } = useObligationProfiles();
  const bulkAssignMutation = useBulkAssignObligations();
  const generateMonthMutation = useGenerateMonthlyObligations();

  // Calculate statistics
  const stats = useMemo(() => {
    if (!clientsWithStatus) return { total: 0, withProfile: 0, withoutProfile: 0 };
    const withProfile = clientsWithStatus.filter(c => c.has_obligation_profile).length;
    return {
      total: clientsWithStatus.length,
      withProfile,
      withoutProfile: clientsWithStatus.length - withProfile
    };
  }, [clientsWithStatus]);

  // Filter clients
  const filteredClients = useMemo(() => {
    if (!clientsWithStatus) return [];
    return clientsWithStatus.filter((c) => {
      const matchesSearch = c.eponimia.toLowerCase().includes(debouncedSearchTerm.toLowerCase()) ||
                           c.afm.includes(debouncedSearchTerm);
      const matchesProfileFilter = !showOnlyWithoutProfiles || !c.has_obligation_profile;
      return matchesSearch && matchesProfileFilter;
    });
  }, [clientsWithStatus, debouncedSearchTerm, showOnlyWithoutProfiles]);

  // Toggle client selection
  const toggleClient = (clientId: number) => {
    if (selectedClientIds.includes(clientId)) {
      setSelectedClientIds(selectedClientIds.filter((id) => id !== clientId));
    } else {
      setSelectedClientIds([...selectedClientIds, clientId]);
    }
  };

  // Toggle type selection
  const toggleType = (typeId: number) => {
    if (selectedTypeIds.includes(typeId)) {
      setSelectedTypeIds(selectedTypeIds.filter((id) => id !== typeId));
    } else {
      setSelectedTypeIds([...selectedTypeIds, typeId]);
    }
  };

  // Toggle profile selection
  const toggleProfile = (profileId: number) => {
    if (selectedProfileIds.includes(profileId)) {
      setSelectedProfileIds(selectedProfileIds.filter((id) => id !== profileId));
    } else {
      setSelectedProfileIds([...selectedProfileIds, profileId]);
    }
  };

  // Select all clients without profiles
  const selectAllWithoutProfiles = () => {
    if (!clientsWithStatus) return;
    const clientIds = clientsWithStatus
      .filter(c => !c.has_obligation_profile)
      .map(c => c.id);
    setSelectedClientIds(clientIds);
  };

  // Select all filtered clients
  const selectAllFiltered = () => {
    setSelectedClientIds(filteredClients.map(c => c.id));
  };

  // Deselect all clients
  const deselectAllClients = () => {
    setSelectedClientIds([]);
  };

  // Handle submit
  const handleSubmit = async () => {
    if (selectedClientIds.length === 0 || (selectedTypeIds.length === 0 && selectedProfileIds.length === 0)) {
      return;
    }

    try {
      const assignResult = await bulkAssignMutation.mutateAsync({
        client_ids: selectedClientIds,
        obligation_type_ids: selectedTypeIds.length > 0 ? selectedTypeIds : undefined,
        obligation_profile_ids: selectedProfileIds.length > 0 ? selectedProfileIds : undefined,
        mode: assignMode,
      });

      // If generateCurrentMonth is true, generate obligations for the current month
      if (generateCurrentMonth) {
        const currentMonth = new Date().getMonth() + 1;
        const currentYear = new Date().getFullYear();
        await generateMonthMutation.mutateAsync({
          month: currentMonth,
          year: currentYear,
          client_ids: selectedClientIds,
        });
      }

      setResult(assignResult);
    } catch (error) {
      console.error('Bulk assign failed:', error);
    }
  };

  // Reset form and close
  const handleClose = () => {
    setSelectedClientIds([]);
    setSelectedTypeIds([]);
    setSelectedProfileIds([]);
    setAssignMode('add');
    setGenerateCurrentMonth(true);
    setSearchTerm('');
    setShowOnlyWithoutProfiles(true);
    setResult(null);
    onClose();
    if (result?.success) {
      onSuccess?.();
    }
  };

  if (!isOpen) return null;

  const isLoading = bulkAssignMutation.isPending || generateMonthMutation.isPending;

  // Show result view
  if (result) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div role="dialog" aria-modal="true" className="bg-white rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center">
              <CheckCircle className="w-6 h-6 text-success-600 mr-2" />
              <h2 className="text-lg font-semibold text-slate-900">Ολοκληρώθηκε</h2>
            </div>
            <button aria-label="Κλείσιμο" onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-lg">
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-success-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-success-700">{result.created_count}</p>
                <p className="text-sm text-success-600">Νέα προφίλ</p>
              </div>
              <div className="bg-brand-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-brand-700">{result.updated_count}</p>
                <p className="text-sm text-brand-600">Ενημερωμένα</p>
              </div>
              <div className="bg-slate-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-slate-700">{result.clients_processed}</p>
                <p className="text-sm text-slate-500">Πελάτες</p>
              </div>
            </div>
            <p className="text-sm text-slate-700 text-center">{result.message}</p>
            {generateCurrentMonth && (
              <div className="bg-brand-50 border border-brand-200 rounded-lg p-3">
                <p className="text-sm text-brand-700">
                  Δημιουργήθηκαν επίσης οι υποχρεώσεις του τρέχοντος μήνα για τους επιλεγμένους πελάτες.
                </p>
              </div>
            )}
          </div>
          <div className="p-4 border-t bg-slate-50">
            <Button onClick={handleClose} className="w-full">
              Κλείσιμο
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div role="dialog" aria-modal="true" className="bg-white rounded-lg w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center">
            <UserPlus className="w-6 h-6 text-brand-600 mr-2" />
            <h2 className="text-lg font-semibold text-slate-900">Μαζική Ανάθεση Υποχρεώσεων</h2>
          </div>
          <button aria-label="Κλείσιμο" onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-lg" disabled={isLoading}>
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <div className="p-4 space-y-4 overflow-y-auto flex-1">
          {/* Statistics */}
          {!isLoadingClients && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-50 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-slate-700">{stats.total}</p>
                <p className="text-xs text-slate-500">Ενεργοί πελάτες</p>
              </div>
              <div className="bg-success-50 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-success-700">{stats.withProfile}</p>
                <p className="text-xs text-success-600">Με υποχρεώσεις</p>
              </div>
              <div className={`rounded-lg p-3 text-center ${stats.withoutProfile > 0 ? 'bg-amber-50' : 'bg-slate-50'}`}>
                <p className={`text-xl font-bold ${stats.withoutProfile > 0 ? 'text-amber-700' : 'text-slate-700'}`}>
                  {stats.withoutProfile}
                </p>
                <p className={`text-xs ${stats.withoutProfile > 0 ? 'text-amber-600' : 'text-slate-500'}`}>
                  Χωρίς υποχρεώσεις
                </p>
              </div>
            </div>
          )}

          {/* Mode Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Τρόπος ανάθεσης</label>
            <div className="flex gap-3">
              <label className={`flex-1 flex items-center gap-2 p-3 border rounded-lg cursor-pointer transition-colors ${
                assignMode === 'add' ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:bg-slate-50'
              }`}>
                <input
                  type="radio"
                  checked={assignMode === 'add'}
                  onChange={() => setAssignMode('add')}
                  className="h-4 w-4 text-brand-600"
                  disabled={isLoading}
                />
                <div>
                  <p className="text-sm font-medium text-slate-900">Προσθήκη</p>
                  <p className="text-xs text-slate-500">Προσθήκη στις υπάρχουσες</p>
                </div>
              </label>
              <label className={`flex-1 flex items-center gap-2 p-3 border rounded-lg cursor-pointer transition-colors ${
                assignMode === 'replace' ? 'border-amber-500 bg-amber-50' : 'border-slate-300 hover:bg-slate-50'
              }`}>
                <input
                  type="radio"
                  checked={assignMode === 'replace'}
                  onChange={() => setAssignMode('replace')}
                  className="h-4 w-4 text-amber-600"
                  disabled={isLoading}
                />
                <div>
                  <p className="text-sm font-medium text-slate-900">Αντικατάσταση</p>
                  <p className="text-xs text-slate-500">Αφαίρεση των παλιών</p>
                </div>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Client Selection */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-slate-700">
                  Πελάτες ({selectedClientIds.length} επιλεγμένοι)
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={selectAllWithoutProfiles}
                    className="text-xs text-amber-600 hover:text-amber-800"
                    disabled={isLoading}
                  >
                    Χωρίς υποχρ.
                  </button>
                  <button
                    type="button"
                    onClick={selectAllFiltered}
                    className="text-xs text-brand-600 hover:text-brand-800"
                    disabled={isLoading}
                  >
                    Όλους
                  </button>
                  <button
                    type="button"
                    onClick={deselectAllClients}
                    className="text-xs text-slate-600 hover:text-slate-800"
                    disabled={isLoading}
                  >
                    Κανένα
                  </button>
                </div>
              </div>

              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="Αναζήτηση..."
                  aria-label="Αναζήτηση πελάτη"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="flex-1 px-2 py-1.5 border border-slate-300 rounded-lg text-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  disabled={isLoading}
                />
                <label className="flex items-center gap-1.5 px-2 py-1.5 bg-slate-50 border border-slate-300 rounded cursor-pointer text-xs">
                  <input
                    type="checkbox"
                    checked={showOnlyWithoutProfiles}
                    onChange={(e) => setShowOnlyWithoutProfiles(e.target.checked)}
                    className="h-3 w-3 text-amber-600 rounded"
                    disabled={isLoading}
                  />
                  Χωρίς
                </label>
              </div>

              <div className="border border-slate-300 rounded-md max-h-60 overflow-y-auto">
                {isLoadingClients ? (
                  <div className="p-4 text-center text-slate-500 text-sm">Φόρτωση...</div>
                ) : filteredClients.length === 0 ? (
                  <div className="p-4 text-center text-slate-500 text-sm">Δεν βρέθηκαν πελάτες</div>
                ) : (
                  filteredClients.map((client) => (
                    <label
                      key={client.id}
                      className={`flex items-center px-2 py-1.5 hover:bg-slate-50 cursor-pointer text-sm ${
                        !client.has_obligation_profile ? 'bg-amber-50/50' : ''
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedClientIds.includes(client.id)}
                        onChange={() => toggleClient(client.id)}
                        className="mr-2 h-4 w-4 text-brand-600 rounded"
                        disabled={isLoading}
                      />
                      <div className="flex-1 min-w-0">
                        <span className="truncate block">{client.eponimia}</span>
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className="text-xs text-slate-500">{client.afm}</span>
                          {client.has_obligation_profile && client.obligation_types_count > 0 && (
                            <span className="text-xs text-success-600">
                              ({client.obligation_types_count} υποχρ.)
                            </span>
                          )}
                          {client.groups_used && client.groups_used.length > 0 && (
                            <span className="text-xs text-brand-600">
                              [{client.groups_used.join(', ')}]
                            </span>
                          )}
                        </div>
                      </div>
                      {!client.has_obligation_profile && (
                        <AlertTriangle className="w-3 h-3 text-amber-500 ml-1" />
                      )}
                    </label>
                  ))
                )}
              </div>
            </div>

            {/* Types and Profiles Selection */}
            <div className="space-y-3">
              {/* Profiles */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">
                  Profiles υποχρεώσεων ({selectedProfileIds.length})
                </label>
                <div className="border border-slate-300 rounded-md max-h-28 overflow-y-auto">
                  {isLoadingProfiles ? (
                    <div className="p-2 text-center text-slate-500 text-sm">Φόρτωση...</div>
                  ) : !profiles || profiles.length === 0 ? (
                    <div className="p-2 text-center text-slate-500 text-sm">Δεν υπάρχουν profiles</div>
                  ) : (
                    profiles.map((profile) => (
                      <label
                        key={profile.id}
                        className="flex items-center px-2 py-1.5 hover:bg-slate-50 cursor-pointer text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={selectedProfileIds.includes(profile.id)}
                          onChange={() => toggleProfile(profile.id)}
                          className="mr-2 h-4 w-4 text-brand-600 rounded"
                          disabled={isLoading}
                        />
                        <div className="flex-1">
                          <span className="font-medium">{profile.name}</span>
                          {profile.description && (
                            <span className="text-slate-500 ml-1">- {profile.description}</span>
                          )}
                        </div>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Obligation Types */}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">
                  Μεμονωμένες υποχρεώσεις ({selectedTypeIds.length})
                </label>
                <div className="border border-slate-300 rounded-md max-h-40 overflow-y-auto">
                  {isLoadingTypes ? (
                    <div className="p-2 text-center text-slate-500 text-sm">Φόρτωση...</div>
                  ) : !typesGrouped || typesGrouped.length === 0 ? (
                    <div className="p-2 text-center text-slate-500 text-sm">Δεν υπάρχουν τύποι</div>
                  ) : (
                    typesGrouped.map((group) => (
                      <div key={group.group_id || 'other'}>
                        <div className="px-2 py-1 bg-slate-100 text-xs font-medium text-slate-600 sticky top-0">
                          {group.group_name}
                        </div>
                        {group.types.map((type) => (
                          <label
                            key={type.id}
                            className="flex items-center px-2 py-1 hover:bg-slate-50 cursor-pointer text-sm"
                          >
                            <input
                              type="checkbox"
                              checked={selectedTypeIds.includes(type.id)}
                              onChange={() => toggleType(type.id)}
                              className="mr-2 h-3 w-3 text-brand-600 rounded"
                              disabled={isLoading}
                            />
                            <span className="text-slate-600 mr-1">{type.code}</span>
                            <span>{type.name}</span>
                          </label>
                        ))}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Generate Current Month Option */}
          <div className="bg-brand-50 border border-brand-200 rounded-lg p-3">
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={generateCurrentMonth}
                onChange={(e) => setGenerateCurrentMonth(e.target.checked)}
                className="mt-0.5 h-4 w-4 text-brand-600 rounded"
                disabled={isLoading}
              />
              <div>
                <p className="text-sm font-medium text-brand-800">
                  Δημιουργία υποχρεώσεων τρέχοντος μήνα
                </p>
                <p className="text-xs text-brand-600">
                  Μετά την ανάθεση, θα δημιουργηθούν αυτόματα οι υποχρεώσεις του τρέχοντος μήνα
                </p>
              </div>
            </label>
          </div>
        </div>

        <div className="flex gap-3 p-4 border-t bg-slate-50">
          <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleSubmit}
            isLoading={isLoading}
            disabled={
              isLoading ||
              selectedClientIds.length === 0 ||
              (selectedTypeIds.length === 0 && selectedProfileIds.length === 0)
            }
            className="flex-1"
          >
            <UserPlus className="w-4 h-4 mr-2" />
            Ανάθεση σε {selectedClientIds.length} πελάτες
          </Button>
        </div>
      </div>
    </div>
  );
}
