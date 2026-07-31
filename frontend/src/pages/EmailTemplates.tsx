/**
 * EmailTemplates.tsx
 * Page for email management - History and Templates with tabs
 */

import { useState } from 'react';
import {
  Mail,
  Plus,
  Edit2,
  Trash2,
  FileText,
  AlertCircle,
  RefreshCw,
  Eye,
  Check,
  Copy,
  Clock,
  Search,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  User,
  Calendar,
  Send,
  ExternalLink,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Modal, ConfirmDialog, Button } from '../components';
import { Badge } from '../components/ui';
import {
  useEmailTemplates,
  useCreateEmailTemplate,
  useUpdateEmailTemplate,
  useDeleteEmailTemplate,
  usePreviewEmail,
  useEmailHistory,
  type EmailTemplateFormData,
} from '../hooks/useEmail';
import { useObligationTypes } from '../hooks/useObligations';
import { useClients } from '../hooks/useClients';
import type { EmailTemplate, EmailLog } from '../types';

// Available variables for templates
const TEMPLATE_VARIABLES = [
  { key: 'client_name', label: 'Επωνυμία πελάτη' },
  { key: 'client_afm', label: 'ΑΦΜ πελάτη' },
  { key: 'client_email', label: 'Email πελάτη' },
  { key: 'obligation_type', label: 'Τύπος υποχρέωσης' },
  { key: 'period_month', label: 'Μήνας περιόδου' },
  { key: 'period_year', label: 'Έτος περιόδου' },
  { key: 'period_display', label: 'Περίοδος (ΜΜ/ΕΕΕΕ)' },
  { key: 'deadline', label: 'Προθεσμία' },
  { key: 'completed_date', label: 'Ημ/νία ολοκλήρωσης' },
  { key: 'accountant_name', label: 'Όνομα λογιστή' },
  { key: 'company_name', label: 'Όνομα εταιρείας' },
];

type TabType = 'history' | 'templates';

export default function EmailTemplates() {
  const [activeTab, setActiveTab] = useState<TabType>('history');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-brand-100 rounded-lg">
            <Mail className="w-6 h-6 text-brand-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Emails</h1>
            <p className="text-sm text-slate-500">Ιστορικό αποστολών και πρότυπα</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'history'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Clock className="w-4 h-4 inline-block mr-2" />
            Ιστορικό Αποστολών
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'templates'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <FileText className="w-4 h-4 inline-block mr-2" />
            Πρότυπα Email
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'history' && <EmailHistoryTab />}
      {activeTab === 'templates' && <EmailTemplatesTab />}
    </div>
  );
}

// ============================================
// EMAIL HISTORY TAB
// ============================================

function EmailHistoryTab() {
  const [filters, setFilters] = useState<{
    client_id?: number;
    status?: 'sent' | 'failed' | 'pending';
    page: number;
    page_size: number;
  }>({
    page: 1,
    page_size: 20,
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEmail, setSelectedEmail] = useState<EmailLog | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useEmailHistory(filters);
  const { data: clients } = useClients({ page_size: 1000 });

  const handleFilterChange = (key: string, value: string | number | undefined) => {
    setFilters(prev => ({
      ...prev,
      [key]: value || undefined,
      page: 1, // Reset to first page on filter change
    }));
  };

  const handleViewDetails = (email: EmailLog) => {
    setSelectedEmail(email);
    setIsDetailModalOpen(true);
  };

  const filteredEmails = data?.results.filter(email => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      email.recipient_email.toLowerCase().includes(term) ||
      email.recipient_name?.toLowerCase().includes(term) ||
      email.subject.toLowerCase().includes(term) ||
      email.client_name?.toLowerCase().includes(term)
    );
  });

  const totalPages = Math.ceil((data?.count || 0) / filters.page_size);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('el-GR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'sent':
        return (
          <Badge variant="success" icon={<CheckCircle className="w-3 h-3" />}>
            Απεστάλη
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="danger" icon={<XCircle className="w-3 h-3" />}>
            Αποτυχία
          </Badge>
        );
      case 'pending':
        return (
          <Badge variant="warning" icon={<Clock className="w-3 h-3" />}>
            Σε αναμονή
          </Badge>
        );
      case 'queued':
        return (
          <Badge variant="info" icon={<Clock className="w-3 h-3" />}>
            Στην ουρά
          </Badge>
        );
      default:
        return status;
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Αναζήτηση σε email, παραλήπτη, θέμα..."
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              />
            </div>
          </div>

          {/* Client Filter */}
          <div className="w-48">
            <select
              value={filters.client_id || ''}
              onChange={(e) => handleFilterChange('client_id', e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            >
              <option value="">Όλοι οι πελάτες</option>
              {clients?.results.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.eponimia}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="w-40">
            <select
              value={filters.status || ''}
              onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            >
              <option value="">Όλες οι καταστάσεις</option>
              <option value="sent">Απεστάλη</option>
              <option value="failed">Αποτυχία</option>
              <option value="pending">Σε αναμονή</option>
            </select>
          </div>

          {/* Refresh */}
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-100 rounded-lg">
              <Send className="w-5 h-5 text-brand-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{data?.count || 0}</p>
              <p className="text-sm text-slate-500">Συνολικά Email</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-success-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-success-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">
                {data?.results.filter(e => e.status === 'sent').length || 0}
              </p>
              <p className="text-sm text-slate-500">Επιτυχή</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-danger-100 rounded-lg">
              <XCircle className="w-5 h-5 text-danger-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">
                {data?.results.filter(e => e.status === 'failed').length || 0}
              </p>
              <p className="text-sm text-slate-500">Αποτυχημένα</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-warning-100 rounded-lg">
              <Clock className="w-5 h-5 text-warning-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">
                {data?.results.filter(e => e.status === 'pending' || e.status === 'queued').length || 0}
              </p>
              <p className="text-sm text-slate-500">Σε αναμονή</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error */}
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

      {/* Loading */}
      {isLoading && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mx-auto mb-4"></div>
          <p className="text-slate-500">Φόρτωση ιστορικού...</p>
        </div>
      )}

      {/* Email List */}
      {!isLoading && !isError && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {filteredEmails?.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Mail className="w-8 h-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                Δεν βρέθηκαν emails
              </h3>
              <p className="text-slate-500">
                {searchTerm || filters.client_id || filters.status
                  ? 'Δοκιμάστε να αλλάξετε τα φίλτρα αναζήτησης'
                  : 'Δεν υπάρχει ακόμα ιστορικό αποστολών email'}
              </p>
            </div>
          ) : (
            <>
              {/* Table Header */}
              <div className="grid grid-cols-12 gap-4 px-4 py-3 bg-slate-50 border-b border-slate-200 text-sm font-medium text-slate-600">
                <div className="col-span-3">Παραλήπτης</div>
                <div className="col-span-4">Θέμα</div>
                <div className="col-span-2">Ημερομηνία</div>
                <div className="col-span-2">Κατάσταση</div>
                <div className="col-span-1"></div>
              </div>

              {/* Table Body */}
              <div className="divide-y divide-slate-100">
                {filteredEmails?.map((email) => (
                  <div
                    key={email.id}
                    className="grid grid-cols-12 gap-4 px-4 py-3 hover:bg-slate-50 transition-colors items-center cursor-pointer"
                  >
                    <div className="col-span-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-brand-100 rounded-full flex items-center justify-center flex-shrink-0">
                          <User className="w-4 h-4 text-brand-600" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-slate-900 truncate">
                            {email.client_name || email.recipient_name || '-'}
                          </p>
                          <p className="text-xs text-slate-500 truncate">
                            {email.recipient_email}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="col-span-4">
                      <p className="text-slate-900 truncate">{email.subject}</p>
                      {email.template_name && (
                        <p className="text-xs text-slate-500">
                          Πρότυπο: {email.template_name}
                        </p>
                      )}
                    </div>
                    <div className="col-span-2">
                      <div className="flex items-center gap-1 text-sm text-slate-600">
                        <Calendar className="w-3 h-3" />
                        {formatDate(email.sent_at)}
                      </div>
                    </div>
                    <div className="col-span-2">
                      {getStatusBadge(email.status)}
                    </div>
                    <div className="col-span-1 flex justify-end gap-1">
                      <button
                        onClick={() => handleViewDetails(email)}
                        className="p-2 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg cursor-pointer transition-colors duration-150"
                        title="Λεπτομέρειες"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      {email.client && (
                        <Link
                          to={`/clients/${email.client}`}
                          className="p-2 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg cursor-pointer transition-colors duration-150"
                          title="Προβολή πελάτη"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                  <p className="text-sm text-slate-600">
                    Σελίδα {filters.page} από {totalPages} ({data?.count} εγγραφές)
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={filters.page <= 1}
                      onClick={() => setFilters(prev => ({ ...prev, page: prev.page - 1 }))}
                    >
                      <ChevronLeft className="w-4 h-4" />
                      Προηγούμενη
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={filters.page >= totalPages}
                      onClick={() => setFilters(prev => ({ ...prev, page: prev.page + 1 }))}
                    >
                      Επόμενη
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Email Detail Modal */}
      <Modal
        isOpen={isDetailModalOpen}
        onClose={() => {
          setIsDetailModalOpen(false);
          setSelectedEmail(null);
        }}
        title="Λεπτομέρειες Email"
        size="lg"
      >
        {selectedEmail && (
          <div className="space-y-4">
            {/* Status Banner */}
            <div className={`p-3 rounded-lg ${
              selectedEmail.status === 'sent' ? 'bg-success-50 border border-success-100' :
              selectedEmail.status === 'failed' ? 'bg-danger-50 border border-danger-100' :
              'bg-warning-50 border border-warning-100'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getStatusBadge(selectedEmail.status)}
                  <span className="text-sm text-slate-600">
                    {formatDate(selectedEmail.sent_at)}
                  </span>
                </div>
                {selectedEmail.sent_by_name && (
                  <span className="text-sm text-slate-600">
                    Από: {selectedEmail.sent_by_name}
                  </span>
                )}
              </div>
              {selectedEmail.error_message && (
                <p className="mt-2 text-sm text-danger-700">
                  <strong>Σφάλμα:</strong> {selectedEmail.error_message}
                </p>
              )}
            </div>

            {/* Recipient Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Παραλήπτης
                </label>
                <p className="text-slate-900">{selectedEmail.recipient_name || '-'}</p>
                <p className="text-sm text-slate-500">{selectedEmail.recipient_email}</p>
              </div>
              {selectedEmail.client_name && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Πελάτης
                  </label>
                  <p className="text-slate-900">{selectedEmail.client_name}</p>
                  {selectedEmail.client_afm && (
                    <p className="text-sm text-slate-500">ΑΦΜ: {selectedEmail.client_afm}</p>
                  )}
                </div>
              )}
            </div>

            {/* Template & Obligation */}
            <div className="grid grid-cols-2 gap-4">
              {selectedEmail.template_name && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Πρότυπο
                  </label>
                  <p className="text-slate-900">{selectedEmail.template_name}</p>
                </div>
              )}
              {selectedEmail.obligation_type && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Υποχρέωση
                  </label>
                  <p className="text-slate-900">{selectedEmail.obligation_type}</p>
                </div>
              )}
            </div>

            {/* Subject */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Θέμα
              </label>
              <p className="p-3 bg-slate-50 rounded-lg text-slate-900">
                {selectedEmail.subject}
              </p>
            </div>

            {/* Body */}
            {selectedEmail.body && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Κείμενο
                </label>
                <div
                  className="p-4 bg-slate-50 rounded-lg prose prose-sm max-w-none max-h-64 overflow-y-auto"
                  dangerouslySetInnerHTML={{ __html: selectedEmail.body }}
                />
              </div>
            )}

            <div className="flex justify-end pt-4 border-t border-slate-200">
              <Button
                variant="secondary"
                onClick={() => {
                  setIsDetailModalOpen(false);
                  setSelectedEmail(null);
                }}
              >
                Κλείσιμο
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ============================================
// EMAIL TEMPLATES TAB
// ============================================

function EmailTemplatesTab() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [previewContent, setPreviewContent] = useState<{ subject: string; body: string } | null>(
    null
  );

  // Queries
  const { data: templates, isLoading, isError, error, refetch } = useEmailTemplates();
  const { data: obligationTypes } = useObligationTypes();

  // Mutations
  const createMutation = useCreateEmailTemplate();
  const updateMutation = useUpdateEmailTemplate();
  const deleteMutation = useDeleteEmailTemplate();
  const previewMutation = usePreviewEmail();

  // Handlers
  const handleCreate = async (data: EmailTemplateFormData) => {
    await createMutation.mutateAsync(data);
    setIsCreateModalOpen(false);
  };

  const handleEdit = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setIsEditModalOpen(true);
  };

  const handleUpdate = async (data: EmailTemplateFormData) => {
    if (!selectedTemplate) return;
    await updateMutation.mutateAsync({ id: selectedTemplate.id, data });
    setIsEditModalOpen(false);
    setSelectedTemplate(null);
  };

  const handleDeleteClick = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedTemplate) return;
    await deleteMutation.mutateAsync(selectedTemplate.id);
    setIsDeleteDialogOpen(false);
    setSelectedTemplate(null);
  };

  const handlePreview = async (template: EmailTemplate) => {
    setSelectedTemplate(template);
    try {
      const result = await previewMutation.mutateAsync({ templateId: template.id });
      setPreviewContent(result);
      setIsPreviewModalOpen(true);
    } catch {
      // Show template without variable substitution
      setPreviewContent({ subject: template.subject, body: template.body_html });
      setIsPreviewModalOpen(true);
    }
  };

  const handleDuplicate = (template: EmailTemplate) => {
    setSelectedTemplate({
      ...template,
      id: 0, // Reset ID for creation
      name: `${template.name} (αντίγραφο)`,
    });
    setIsCreateModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="flex justify-end">
        <Button onClick={() => setIsCreateModalOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Νέο Πρότυπο
        </Button>
      </div>

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
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600 mx-auto mb-4"></div>
          <p className="text-slate-500">Φόρτωση προτύπων...</p>
        </div>
      )}

      {/* Templates List */}
      {!isLoading && !isError && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
          {templates?.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-brand-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText className="w-8 h-8 text-brand-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                Δεν υπάρχουν πρότυπα
              </h3>
              <p className="text-slate-500 mb-6">
                Δημιουργήστε το πρώτο σας πρότυπο email για να στέλνετε ειδοποιήσεις στους πελάτες.
              </p>
              <Button onClick={() => setIsCreateModalOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Δημιουργία Προτύπου
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {templates?.map((template) => (
                <div
                  key={template.id}
                  className="p-4 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-slate-900 truncate">
                          {template.name}
                        </h3>
                        {template.is_active ? (
                          <span className="px-2 py-0.5 text-xs font-medium bg-success-100 text-success-700 rounded-full">
                            Ενεργό
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-600 rounded-full">
                            Ανενεργό
                          </span>
                        )}
                        {template.obligation_type_name && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-brand-100 text-brand-800 rounded-full">
                            {template.obligation_type_name}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mb-1">
                        <strong>Θέμα:</strong> {template.subject}
                      </p>
                      {template.description && (
                        <p className="text-sm text-slate-500">{template.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handlePreview(template)}
                        className="p-2 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg cursor-pointer transition-colors duration-150"
                        title="Προεπισκόπηση"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDuplicate(template)}
                        className="p-2 text-slate-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg cursor-pointer transition-colors duration-150"
                        title="Αντιγραφή"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleEdit(template)}
                        className="p-2 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg cursor-pointer transition-colors duration-150"
                        title="Επεξεργασία"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteClick(template)}
                        className="p-2 text-slate-500 hover:text-danger-600 hover:bg-danger-50 rounded-lg cursor-pointer transition-colors duration-150"
                        title="Διαγραφή"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Variables Reference */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">
          Διαθέσιμες Μεταβλητές
        </h3>
        <p className="text-sm text-slate-600 mb-4">
          Χρησιμοποιήστε αυτές τις μεταβλητές στο θέμα και το κείμενο του email.
          Θα αντικατασταθούν αυτόματα με τα πραγματικά δεδομένα.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {TEMPLATE_VARIABLES.map((variable) => (
            <div
              key={variable.key}
              className="bg-slate-50 rounded-lg p-3 text-sm"
            >
              <code className="text-brand-600 font-mono">{`{${variable.key}}`}</code>
              <p className="text-slate-600 mt-1">{variable.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false);
          setSelectedTemplate(null);
        }}
        title="Νέο Πρότυπο Email"
        size="xl"
      >
        <EmailTemplateForm
          initialData={selectedTemplate || undefined}
          obligationTypes={obligationTypes || []}
          onSubmit={handleCreate}
          onCancel={() => {
            setIsCreateModalOpen(false);
            setSelectedTemplate(null);
          }}
          isLoading={createMutation.isPending}
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setSelectedTemplate(null);
        }}
        title="Επεξεργασία Προτύπου"
        size="xl"
      >
        <EmailTemplateForm
          initialData={selectedTemplate || undefined}
          obligationTypes={obligationTypes || []}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditModalOpen(false);
            setSelectedTemplate(null);
          }}
          isLoading={updateMutation.isPending}
        />
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSelectedTemplate(null);
        }}
        onConfirm={handleDeleteConfirm}
        title="Διαγραφή Προτύπου"
        message={`Είστε σίγουροι ότι θέλετε να διαγράψετε το πρότυπο "${selectedTemplate?.name}";`}
        confirmText="Διαγραφή"
        cancelText="Ακύρωση"
        isLoading={deleteMutation.isPending}
        variant="danger"
      />

      {/* Preview Modal */}
      <Modal
        isOpen={isPreviewModalOpen}
        onClose={() => {
          setIsPreviewModalOpen(false);
          setPreviewContent(null);
        }}
        title={`Προεπισκόπηση: ${selectedTemplate?.name || ''}`}
        size="lg"
      >
        {previewContent && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Θέμα
              </label>
              <div className="p-3 bg-slate-50 rounded-lg text-slate-900">
                {previewContent.subject}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Κείμενο
              </label>
              <div
                className="p-4 bg-slate-50 rounded-lg prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: previewContent.body }}
              />
            </div>
            <div className="flex justify-end pt-4 border-t border-slate-200">
              <Button
                variant="secondary"
                onClick={() => {
                  setIsPreviewModalOpen(false);
                  setPreviewContent(null);
                }}
              >
                Κλείσιμο
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ============================================
// EMAIL TEMPLATE FORM COMPONENT
// ============================================

interface EmailTemplateFormProps {
  initialData?: Partial<EmailTemplate>;
  obligationTypes: Array<{ id: number; code: string; name: string }>;
  onSubmit: (data: EmailTemplateFormData) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

function EmailTemplateForm({
  initialData,
  obligationTypes,
  onSubmit,
  onCancel,
  isLoading = false,
}: EmailTemplateFormProps) {
  const [formData, setFormData] = useState<EmailTemplateFormData>({
    name: initialData?.name || '',
    description: initialData?.description || '',
    subject: initialData?.subject || '',
    body_html: initialData?.body_html || '',
    obligation_type: initialData?.obligation_type || null,
    is_active: initialData?.is_active ?? true,
  });
  const [error, setError] = useState<string | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value,
    }));
  };

  const insertVariable = (variable: string, field: 'subject' | 'body_html') => {
    const placeholder = `{${variable}}`;
    setFormData((prev) => ({
      ...prev,
      [field]: prev[field] + placeholder,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.name.trim()) {
      setError('Το όνομα είναι υποχρεωτικό');
      return;
    }
    if (!formData.subject.trim()) {
      setError('Το θέμα είναι υποχρεωτικό');
      return;
    }
    if (!formData.body_html.trim()) {
      setError('Το κείμενο είναι υποχρεωτικό');
      return;
    }

    try {
      await onSubmit({
        ...formData,
        obligation_type: formData.obligation_type || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Σφάλμα κατά την αποθήκευση');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-danger-50 border border-danger-100 rounded-lg p-3 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-danger-600 flex-shrink-0" />
          <span className="text-sm text-danger-700">{error}</span>
        </div>
      )}

      {/* Name */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Όνομα Προτύπου *
        </label>
        <input
          type="text"
          name="name"
          value={formData.name}
          onChange={handleChange}
          placeholder="π.χ. Ειδοποίηση ολοκλήρωσης ΦΠΑ"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        />
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Περιγραφή
        </label>
        <input
          type="text"
          name="description"
          value={formData.description}
          onChange={handleChange}
          placeholder="Σύντομη περιγραφή του προτύπου"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        />
      </div>

      {/* Obligation Type */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Τύπος Υποχρέωσης (αυτόματη επιλογή)
        </label>
        <select
          name="obligation_type"
          value={formData.obligation_type || ''}
          onChange={(e) =>
            setFormData((prev) => ({
              ...prev,
              obligation_type: e.target.value ? Number(e.target.value) : null,
            }))
          }
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        >
          <option value="">-- Κανένας (χειροκίνητη επιλογή) --</option>
          {obligationTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.code} - {type.name}
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-500 mt-1">
          Αν οριστεί, το πρότυπο επιλέγεται αυτόματα για αυτόν τον τύπο υποχρέωσης
        </p>
      </div>

      {/* Subject */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Θέμα Email *
        </label>
        <input
          type="text"
          name="subject"
          value={formData.subject}
          onChange={handleChange}
          placeholder="π.χ. Ολοκλήρωση {obligation_type} - {period_display}"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
        />
        <div className="flex flex-wrap gap-1 mt-2">
          {['client_name', 'obligation_type', 'period_display'].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => insertVariable(v, 'subject')}
              className="px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded hover:bg-slate-200 cursor-pointer transition-colors duration-150"
            >
              {`{${v}}`}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">
          Κείμενο Email *
        </label>
        <textarea
          name="body_html"
          value={formData.body_html}
          onChange={handleChange}
          rows={10}
          placeholder="Αγαπητέ/ή {client_name},&#10;&#10;Σας ενημερώνουμε ότι η υποχρέωση {obligation_type} για την περίοδο {period_display} ολοκληρώθηκε."
          className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 font-mono text-sm"
        />
        <div className="flex flex-wrap gap-1 mt-2">
          {TEMPLATE_VARIABLES.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => insertVariable(v.key, 'body_html')}
              className="px-2 py-1 text-xs bg-slate-100 text-slate-700 rounded hover:bg-slate-200 cursor-pointer transition-colors duration-150"
              title={v.label}
            >
              {`{${v.key}}`}
            </button>
          ))}
        </div>
      </div>

      {/* Is Active */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
          className="w-4 h-4 text-brand-600 rounded"
        />
        <span className="text-sm text-slate-700">Ενεργό πρότυπο</span>
      </label>

      {/* Actions */}
      <div className="flex gap-3 pt-4 border-t border-slate-200">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isLoading}>
          Ακύρωση
        </Button>
        <Button type="submit" isLoading={isLoading} className="flex-1">
          <Check className="w-4 h-4 mr-2" />
          Αποθήκευση
        </Button>
      </div>
    </form>
  );
}
