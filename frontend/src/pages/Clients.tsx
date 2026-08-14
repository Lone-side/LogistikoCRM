import { useState, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useClients, useCreateClient, useDeleteClient, useDebounce } from '../hooks';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import { Modal, ConfirmDialog, ClientForm, Button, TableSkeleton } from '../components';
import { useToast } from '../hooks/useToast';
import { Users, Search, AlertCircle, RefreshCw, Plus, Edit2, Trash2, Eye, Download, Upload, FileDown, FileUp } from 'lucide-react';
import type { Client, ClientFormData } from '../types';
import { PageHeader, EmptyState, Badge } from '../components/ui';
import { downloadClientsCSV, downloadClientsTemplate, useImportClients } from '../hooks/useExportImport';

export default function Clients() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebounce(searchTerm, 300);
  const [page, setPage] = useState(1);
  const pageSize = 100;

  // Modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const { data, isLoading, isError, error, refetch } = useClients({ page, page_size: pageSize });
  const createMutation = useCreateClient();
  const deleteMutation = useDeleteClient();
  const importMutation = useImportClients();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Update client mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<ClientFormData> }) => {
      const response = await apiClient.patch<Client>(`/api/v1/clients/${id}/`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
  });

  // Filter clients by name (eponimia) or AFM - uses debounced search term for performance
  const filteredClients = useMemo(() => {
    if (!data?.results) return [];
    if (!debouncedSearchTerm.trim()) return data.results;

    const term = debouncedSearchTerm.toLowerCase().trim();
    return data.results.filter(
      (client) =>
        (client.eponimia?.toLowerCase() || '').includes(term) ||
        (client.afm || '').includes(term)
    );
  }, [data, debouncedSearchTerm]);

  // Handlers
  const handleCreate = (formData: ClientFormData) => {
    createMutation.mutate(formData, {
      onSuccess: () => {
        setIsCreateModalOpen(false);
        // invalidateQueries in hook triggers automatic refetch
      },
    });
  };

  const handleEdit = (client: Client) => {
    setSelectedClient(client);
    setIsEditModalOpen(true);
  };

  const handleUpdate = (formData: ClientFormData) => {
    if (!selectedClient) return;
    updateMutation.mutate(
      { id: selectedClient.id, data: formData },
      {
        onSuccess: () => {
          setIsEditModalOpen(false);
          setSelectedClient(null);
          showToast('success', 'Ο πελάτης ενημερώθηκε επιτυχώς');
        },
        onError: (error: unknown) => {
          // Extract error message from axios response
          let message = 'Σφάλμα κατά την ενημέρωση';
          if (error && typeof error === 'object' && 'response' in error) {
            const axiosError = error as { response?: { data?: Record<string, string[]> } };
            const data = axiosError.response?.data;
            if (data) {
              // Get first validation error message
              const firstKey = Object.keys(data)[0];
              if (firstKey && Array.isArray(data[firstKey])) {
                message = `${firstKey}: ${data[firstKey][0]}`;
              } else if (typeof data === 'string') {
                message = data;
              }
            }
          } else if (error instanceof Error) {
            message = error.message;
          }
          showToast('error', message);
        },
      }
    );
  };

  const handleDeleteClick = (client: Client) => {
    setSelectedClient(client);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!selectedClient) return;
    deleteMutation.mutate(selectedClient.id, {
      onSuccess: () => {
        setIsDeleteDialogOpen(false);
        setSelectedClient(null);
        // invalidateQueries in hook triggers automatic refetch
      },
      onError: (error: unknown) => {
        setIsDeleteDialogOpen(false);
        setSelectedClient(null);
        const status =
          error && typeof error === 'object' && 'response' in error
            ? (error as { response?: { status?: number } }).response?.status
            : undefined;
        alert(
          status === 403
            ? 'Η διαγραφή πελάτη επιτρέπεται μόνο σε διαχειριστές.'
            : 'Η διαγραφή απέτυχε. Δοκιμάστε ξανά.'
        );
      },
    });
  };

  const handleLoadMore = () => {
    setPage((prev) => prev + 1);
  };

  const hasMore = data?.next !== null;
  const totalCount = data?.count || 0;
  const loadedCount = data?.results?.length || 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        className="mb-0"
        title={
          <span className="flex items-center gap-3">
            <span className="p-2 bg-brand-50 rounded-lg">
              <Users className="w-6 h-6 text-brand-600" />
            </span>
            Πελάτες
          </span>
        }
        subtitle={`${totalCount} συνολικά`}
        actions={
          <>
          {/* Export/Import Dropdown */}
          <div className="relative" ref={exportMenuRef}>
            <Button
              variant="secondary"
              onClick={() => setShowExportMenu(!showExportMenu)}
            >
              <Download className="w-4 h-4 mr-2" />
              Εξαγωγή/Εισαγωγή
            </Button>
            {showExportMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-50">
                <button
                  onClick={async () => {
                    try {
                      await downloadClientsCSV();
                      showToast('success', 'Η εξαγωγή ξεκίνησε');
                    } catch {
                      showToast('error', 'Σφάλμα κατά την εξαγωγή');
                    }
                    setShowExportMenu(false);
                  }}
                  className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <FileDown className="w-4 h-4" />
                  Εξαγωγή πελατών (Excel)
                </button>
                <button
                  onClick={async () => {
                    try {
                      await downloadClientsTemplate();
                      showToast('success', 'Λήψη template');
                    } catch {
                      showToast('error', 'Σφάλμα');
                    }
                    setShowExportMenu(false);
                  }}
                  className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <FileDown className="w-4 h-4" />
                  Λήψη template Excel
                </button>
                <div className="border-t border-slate-100 my-1" />
                <button
                  onClick={() => {
                    setIsImportModalOpen(true);
                    setShowExportMenu(false);
                  }}
                  className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <FileUp className="w-4 h-4" />
                  Εισαγωγή πελατών (Excel)
                </button>
              </div>
            )}
          </div>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Νέος Πελάτης
          </Button>
          </>
        }
      />

      {/* Search Box */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            placeholder="Αναζήτηση με επωνυμία ή ΑΦΜ..."
            aria-label="Αναζήτηση με επωνυμία ή ΑΦΜ"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg transition-colors duration-150 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Error Banner */}
      {isError && (
        <div className="bg-danger-50 border border-danger-100 rounded-xl p-4">
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
        <TableSkeleton rows={8} columns={5} showAvatar />
      )}

      {/* Clients Table */}
      {!isLoading && !isError && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
            <p className="text-sm text-slate-600">
              {filteredClients.length} από {totalCount} πελάτες
              {searchTerm && ` (φίλτρο: "${searchTerm}")`}
            </p>
          </div>

          {filteredClients.length === 0 ? (
            <EmptyState
              icon={Users}
              title={
                searchTerm
                  ? 'Δεν βρέθηκαν πελάτες με αυτά τα κριτήρια αναζήτησης.'
                  : 'Δεν υπάρχουν πελάτες.'
              }
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                        Επωνυμία
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                        ΑΦΜ
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                        Τηλέφωνο
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                        Email
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wide">
                        Ενέργειες
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-100">
                    {filteredClients.map((client) => (
                      <tr key={client.id} className="hover:bg-slate-50 transition-colors duration-150">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <Link to={`/clients/${client.id}`} className="flex items-center group cursor-pointer">
                            <div className="flex-shrink-0 h-10 w-10 bg-brand-50 rounded-full flex items-center justify-center group-hover:bg-brand-100 transition-colors duration-150">
                              <span className="text-brand-600 font-medium text-sm">
                                {(client.eponimia || 'Π').charAt(0).toUpperCase()}
                              </span>
                            </div>
                            <div className="ml-4">
                              <div className="text-sm font-medium text-slate-900 group-hover:text-brand-600 transition-colors duration-150">
                                {client.eponimia}
                              </div>
                              {client.is_active === false && (
                                <Badge variant="neutral">Ανενεργός</Badge>
                              )}
                            </div>
                          </Link>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="font-mono text-sm text-slate-900">{client.afm}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                          {client.kinito_tilefono || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                          {client.email || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <Link
                            to={`/clients/${client.id}`}
                            className="text-slate-600 hover:text-slate-900 mr-3 p-1.5 hover:bg-slate-50 rounded-lg transition-colors duration-150 inline-block cursor-pointer"
                            title="Προβολή"
                          >
                            <Eye className="w-4 h-4" />
                          </Link>
                          <button
                            onClick={() => handleEdit(client)}
                            className="text-brand-600 hover:text-brand-800 mr-3 p-1.5 hover:bg-brand-50 rounded-lg transition-colors duration-150 cursor-pointer"
                            title="Επεξεργασία"
                            aria-label="Επεξεργασία"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteClick(client)}
                            className="text-danger-600 hover:text-danger-700 p-1.5 hover:bg-danger-50 rounded-lg transition-colors duration-150 cursor-pointer"
                            title="Διαγραφή"
                            aria-label="Διαγραφή"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Load More */}
              {hasMore && !searchTerm && (
                <div className="px-6 py-4 border-t border-slate-200 text-center">
                  <Button variant="secondary" onClick={handleLoadMore}>
                    Φόρτωση περισσότερων ({loadedCount} από {totalCount})
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
        title="Νέος Πελάτης"
      >
        <ClientForm
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
          setSelectedClient(null);
        }}
        title="Επεξεργασία Πελάτη"
      >
        <ClientForm
          client={selectedClient}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditModalOpen(false);
            setSelectedClient(null);
          }}
          isLoading={updateMutation.isPending}
        />
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSelectedClient(null);
        }}
        onConfirm={handleDeleteConfirm}
        title="Διαγραφή Πελάτη"
        message={`Είστε σίγουροι ότι θέλετε να διαγράψετε τον πελάτη "${selectedClient?.eponimia}";`}
        confirmText="Διαγραφή"
        cancelText="Ακύρωση"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />

      {/* Import Modal */}
      <ImportClientsModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        importMutation={importMutation}
        showToast={showToast}
        refetch={refetch}
      />
    </div>
  );
}

// ============================================
// IMPORT CLIENTS MODAL COMPONENT
// ============================================

interface ImportClientsModalProps {
  isOpen: boolean;
  onClose: () => void;
  importMutation: ReturnType<typeof useImportClients>;
  showToast: (type: 'success' | 'error' | 'info', message: string) => void;
  refetch: () => void;
}

function ImportClientsModal({
  isOpen,
  onClose,
  importMutation,
  showToast,
  refetch,
}: ImportClientsModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'skip' | 'update'>('skip');
  const [result, setResult] = useState<{
    created_count: number;
    updated_count: number;
    skipped_count?: number;
    errors: string[];
    message: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
    }
  };

  const handleImport = async () => {
    if (!file) {
      showToast('error', 'Επιλέξτε αρχείο');
      return;
    }

    try {
      const res = await importMutation.mutateAsync({ file, mode });
      setResult(res);
      showToast('success', res.message);
      refetch();
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : 'Σφάλμα εισαγωγής';
      showToast('error', errMsg);
    }
  };

  const handleClose = () => {
    setFile(null);
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={handleClose} />

        <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg">
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Upload className="w-5 h-5 text-brand-600" />
              Εισαγωγή Πελατών
            </h3>
          </div>

          {/* Content */}
          <div className="px-6 py-4 space-y-4">
            {/* File Input */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Αρχείο Excel (.xlsx)
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
              />
              {file && (
                <p className="mt-2 text-sm text-slate-500">
                  Επιλεγμένο: {file.name}
                </p>
              )}
            </div>

            {/* Mode Selection */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Τρόπος εισαγωγής
              </label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="importMode"
                    value="skip"
                    checked={mode === 'skip'}
                    onChange={() => setMode('skip')}
                    className="w-4 h-4 text-brand-600"
                  />
                  <span className="text-sm text-slate-700">
                    Παράλειψη υπαρχόντων (μόνο νέοι πελάτες)
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="importMode"
                    value="update"
                    checked={mode === 'update'}
                    onChange={() => setMode('update')}
                    className="w-4 h-4 text-brand-600"
                  />
                  <span className="text-sm text-slate-700">
                    Ενημέρωση υπαρχόντων (αντικατάσταση δεδομένων)
                  </span>
                </label>
              </div>
            </div>

            {/* Result */}
            {result && (
              <div className="p-4 bg-slate-50 rounded-lg">
                <h4 className="font-medium text-slate-900 mb-2">Αποτελέσματα:</h4>
                <ul className="text-sm text-slate-600 space-y-1">
                  <li>Δημιουργήθηκαν: {result.created_count}</li>
                  <li>Ενημερώθηκαν: {result.updated_count}</li>
                  {result.skipped_count !== undefined && (
                    <li>Παραλείφθηκαν: {result.skipped_count}</li>
                  )}
                </ul>
                {result.errors.length > 0 && (
                  <div className="mt-3">
                    <h5 className="text-sm font-medium text-danger-600">Σφάλματα:</h5>
                    <ul className="text-xs text-danger-600 mt-1 max-h-32 overflow-y-auto">
                      {result.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
            <Button variant="secondary" onClick={handleClose}>
              Κλείσιμο
            </Button>
            <Button
              onClick={handleImport}
              disabled={!file || importMutation.isPending}
            >
              {importMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Εισαγωγή...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Εισαγωγή
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
