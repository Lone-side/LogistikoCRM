import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  User,
  FileText,
  Mail,
  Phone,
  Ticket,
  StickyNote,
  ChevronLeft,
  Save,
  AlertCircle,
  RefreshCw,
  ClipboardList,
  FolderOpen,
} from 'lucide-react';
import { Button } from '../components';
import {
  useClientFull,
  useClientDocuments,
  useClientObligations,
  useClientEmails,
  useClientCalls,
  useClientTickets,
  useUploadDocument,
  useDeleteDocument,
  useCreateTicket,
  useUpdateTicket,
  useDeleteTicket,
  useUpdateClientFull,
  useClientObligationProfile,
  useUpdateClientObligationProfile,
} from '../hooks/useClientDetails';
import type { ClientDocumentFilters } from '../hooks/useClientDetails';
import { useObligationTypesGrouped } from '../hooks/useObligations';
import { useObligationProfilesList } from '../hooks/useObligationSettings';
import type { ClientFull } from '../types';

// Import tab components
import {
  ClientInfoTab,
  ClientObligationsTab,
  ClientProfileTab,
  ClientDocumentsTab,
  ClientEmailsTab,
  ClientCallsTab,
  ClientTicketsTab,
  ClientNotesTab,
  UploadModal,
  CreateTicketModal,
  type TicketUpdateData,
} from '../components/client';

// Tab type
type TabType = 'info' | 'obligations' | 'profile' | 'documents' | 'emails' | 'calls' | 'tickets' | 'notes';

// Tab configuration
const TABS: { id: TabType; label: string; icon: React.ElementType }[] = [
  { id: 'info', label: 'Στοιχεία', icon: User },
  { id: 'obligations', label: 'Υποχρεώσεις', icon: FileText },
  { id: 'profile', label: 'Προφίλ Υποχρεώσεων', icon: ClipboardList },
  { id: 'documents', label: 'Έγγραφα', icon: FileText },
  { id: 'emails', label: 'Email', icon: Mail },
  { id: 'calls', label: 'Κλήσεις', icon: Phone },
  { id: 'tickets', label: 'Tickets', icon: Ticket },
  { id: 'notes', label: 'Σημειώσεις', icon: StickyNote },
];

export default function ClientDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const clientId = parseInt(id || '0', 10);

  const [activeTab, setActiveTab] = useState<TabType>('info');
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<ClientFull>>({});
  const [yearFilter, setYearFilter] = useState<number>(new Date().getFullYear());
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [docFilters, setDocFilters] = useState<ClientDocumentFilters>({});
  const [ticketModalOpen, setTicketModalOpen] = useState(false);

  // Fetch client data
  const { data: client, isLoading, isError, error, refetch } = useClientFull(clientId);

  // Tab-specific queries (lazy loaded)
  const { data: documentsData, isLoading: docsLoading } = useClientDocuments(
    clientId,
    docFilters
  );
  const { data: obligationsData, isLoading: oblLoading } = useClientObligations(
    clientId,
    activeTab === 'obligations' ? { year: yearFilter, status: statusFilter || undefined } : undefined
  );
  const { data: emailsData, isLoading: emailsLoading } = useClientEmails(clientId);
  const { data: callsData, isLoading: callsLoading } = useClientCalls(clientId);
  const { data: ticketsData, isLoading: ticketsLoading } = useClientTickets(clientId);

  // Obligation Profile hooks
  const { data: obligationTypesGrouped, isLoading: typesLoading } = useObligationTypesGrouped();
  const { data: obligationProfiles, isLoading: profilesListLoading } = useObligationProfilesList();
  const { data: clientObligationProfile, isLoading: profileLoading } = useClientObligationProfile(clientId);
  const updateProfileMutation = useUpdateClientObligationProfile(clientId);

  // Mutations
  const updateMutation = useUpdateClientFull(clientId);
  const uploadMutation = useUploadDocument(clientId);
  const deleteMutation = useDeleteDocument(clientId);
  const createTicketMutation = useCreateTicket(clientId);
  const updateTicketMutation = useUpdateTicket(clientId);
  const deleteTicketMutation = useDeleteTicket(clientId);

  // Handlers
  const handleSave = useCallback(() => {
    updateMutation.mutate(editData, {
      onSuccess: () => {
        setIsEditing(false);
        setEditData({});
        refetch();
      },
    });
  }, [editData, updateMutation, refetch]);

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditData({});
  }, []);

  const handleFieldChange = useCallback((field: keyof ClientFull, value: unknown) => {
    setEditData((prev) => ({ ...prev, [field]: value }));
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-500">Φόρτωση στοιχείων πελάτη...</span>
      </div>
    );
  }

  if (isError || !client) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-red-800 mb-2">Σφάλμα φόρτωσης</h2>
        <p className="text-red-600 mb-4">
          {error instanceof Error ? error.message : 'Δεν βρέθηκε ο πελάτης'}
        </p>
        <Button variant="secondary" onClick={() => navigate('/clients')}>
          <ChevronLeft className="w-4 h-4 mr-2" />
          Επιστροφή στους πελάτες
        </Button>
      </div>
    );
  }

  const currentData = { ...client, ...editData };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Back button and client info */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/clients')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
                <span className="text-2xl font-bold text-blue-600">
                  {client.eponimia.charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{client.eponimia}</h1>
                <div className="flex items-center gap-3 mt-1">
                  <span className="font-mono text-sm bg-gray-100 px-2 py-0.5 rounded">
                    ΑΦΜ: {client.afm}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-xs font-medium rounded ${
                      client.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {client.is_active ? 'Ενεργός' : 'Ανενεργός'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {/* Folder link - opens Django archive view */}
            <a
              href={`/accounting/client/${clientId}/files/`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium rounded-lg transition-colors"
              title="Άνοιγμα φακέλου αρχείων"
            >
              <FolderOpen className="w-4 h-4 mr-2" />
              Φάκελος
            </a>
            {isEditing ? (
              <>
                <Button
                  variant="secondary"
                  onClick={handleCancelEdit}
                  disabled={updateMutation.isPending}
                >
                  Ακύρωση
                </Button>
                <Button onClick={handleSave} disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Αποθήκευση
                </Button>
              </>
            ) : (
              <Button onClick={() => setIsEditing(true)}>
                <Save className="w-4 h-4 mr-2" />
                Επεξεργασία
              </Button>
            )}
          </div>
        </div>

        {/* Stats cards */}
        {client.counts && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-200">
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">{client.counts.obligations}</p>
              <p className="text-sm text-gray-500">Υποχρεώσεις</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-600">{client.counts.pending_obligations}</p>
              <p className="text-sm text-gray-500">Εκκρεμείς</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{client.counts.documents}</p>
              <p className="text-sm text-gray-500">Έγγραφα</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-purple-600">{client.counts.open_tickets}</p>
              <p className="text-sm text-gray-500">Ανοιχτά Tickets</p>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {/* Tab navigation */}
        <div className="flex overflow-x-auto border-b border-gray-200">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-6">
          {/* INFO TAB */}
          {activeTab === 'info' && (
            <ClientInfoTab
              client={currentData as ClientFull}
              clientId={clientId}
              isEditing={isEditing}
              onFieldChange={handleFieldChange}
            />
          )}

          {/* OBLIGATIONS TAB */}
          {activeTab === 'obligations' && (
            <ClientObligationsTab
              clientId={clientId}
              data={obligationsData}
              isLoading={oblLoading}
              yearFilter={yearFilter}
              setYearFilter={setYearFilter}
              statusFilter={statusFilter}
              setStatusFilter={setStatusFilter}
            />
          )}

          {/* OBLIGATION PROFILE TAB */}
          {activeTab === 'profile' && (
            <ClientProfileTab
              groupedTypes={obligationTypesGrouped || []}
              profiles={obligationProfiles || []}
              clientProfile={clientObligationProfile}
              isLoading={typesLoading || profileLoading || profilesListLoading}
              onSave={(typeIds, profileIds) => {
                updateProfileMutation.mutate({
                  obligation_type_ids: typeIds,
                  obligation_profile_ids: profileIds,
                });
              }}
              isSaving={updateProfileMutation.isPending}
            />
          )}

          {/* DOCUMENTS TAB */}
          {activeTab === 'documents' && (
            <ClientDocumentsTab
              data={documentsData}
              isLoading={docsLoading}
              filters={docFilters}
              onFiltersChange={setDocFilters}
              onUpload={() => setUploadModalOpen(true)}
              onDelete={(docId) => {
                if (confirm('Διαγραφή εγγράφου;')) {
                  deleteMutation.mutate(docId);
                }
              }}
            />
          )}

          {/* EMAILS TAB */}
          {activeTab === 'emails' && (
            <ClientEmailsTab data={emailsData} isLoading={emailsLoading} />
          )}

          {/* CALLS TAB */}
          {activeTab === 'calls' && (
            <ClientCallsTab data={callsData} isLoading={callsLoading} />
          )}

          {/* TICKETS TAB */}
          {activeTab === 'tickets' && (
            <ClientTicketsTab
              data={ticketsData}
              isLoading={ticketsLoading}
              onCreate={() => setTicketModalOpen(true)}
              onUpdate={(ticketId, data: TicketUpdateData) => updateTicketMutation.mutate({ ticketId, data })}
              onDelete={(ticketId) => deleteTicketMutation.mutate(ticketId)}
              isUpdating={updateTicketMutation.isPending}
              isDeleting={deleteTicketMutation.isPending}
            />
          )}

          {/* NOTES TAB */}
          {activeTab === 'notes' && (
            <ClientNotesTab
              client={currentData as ClientFull}
              isEditing={isEditing}
              onFieldChange={handleFieldChange}
            />
          )}
        </div>
      </div>

      {/* Upload Modal */}
      {uploadModalOpen && (
        <UploadModal
          onClose={() => {
            setUploadModalOpen(false);
            setUploadError(null);
          }}
          onUpload={(file, category, description, year, month) => {
            setUploadError(null);
            uploadMutation.mutate(
              { file, category, description, year, month },
              {
                onSuccess: () => setUploadModalOpen(false),
                onError: (err) => {
                  const axiosErr = err as { response?: { data?: { error?: string } } };
                  setUploadError(
                    axiosErr.response?.data?.error || 'Σφάλμα κατά τη μεταφόρτωση'
                  );
                },
              }
            );
          }}
          isLoading={uploadMutation.isPending}
          errorMessage={uploadError}
          clientId={clientId}
        />
      )}

      {/* Create Ticket Modal */}
      {ticketModalOpen && (
        <CreateTicketModal
          onClose={() => setTicketModalOpen(false)}
          onCreate={(title, description, priority) => {
            createTicketMutation.mutate(
              { title, description, priority },
              {
                onSuccess: () => setTicketModalOpen(false),
              }
            );
          }}
          isLoading={createTicketMutation.isPending}
        />
      )}
    </div>
  );
}
