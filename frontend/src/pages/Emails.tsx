/**
 * Emails.tsx
 * Email Management page with tabs for History, Templates, and Recipient Lists
 */

import { useState, useEffect } from 'react';
import {
  Mail,
  Send,
  FileText,
  Users,
  Plus,
  Search,
  Trash2,
  Edit2,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../components';
import { Modal } from '../components/Modal';
import apiClient from '../api/client';

// Types
interface EmailLog {
  id: number;
  recipient_email: string;
  recipient_name: string;
  client_name: string | null;
  subject: string;
  status: string;
  status_display: string;
  sent_at: string;
  sent_by_name: string | null;
}

interface EmailTemplate {
  id: number;
  name: string;
  description: string;
  subject: string;
  body_html: string;
  requires_approval: boolean;
  is_active: boolean;
}

interface RecipientList {
  id: number;
  name: string;
  description: string;
  client_count: number;
  email_count: number;
  requires_approval: boolean;
  clients_data: Array<{
    id: number;
    eponimia: string;
    afm: string;
    email: string;
  }>;
}

interface Client {
  id: number;
  eponimia?: string;
  onoma?: string;
  afm: string;
  email?: string;
}

type TabType = 'history' | 'templates' | 'lists';

export default function Emails() {
  const [activeTab, setActiveTab] = useState<TabType>('history');
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [isListModalOpen, setIsListModalOpen] = useState(false);
  const [editingList, setEditingList] = useState<RecipientList | null>(null);

  // Data states
  const [emailHistory, setEmailHistory] = useState<EmailLog[]>([]);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [recipientLists, setRecipientLists] = useState<RecipientList[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Compose form state
  const [composeForm, setComposeForm] = useState({
    recipientType: 'client' as 'client' | 'list',
    clientId: '',
    listId: '',
    templateId: '',
    subject: '',
    body: '',
  });
  const [sending, setSending] = useState(false);

  // List form state
  const [listForm, setListForm] = useState({
    name: '',
    description: '',
    requires_approval: true,
    selectedClients: [] as number[],
  });

  // Fetch data on mount and tab change
  useEffect(() => {
    if (activeTab === 'history') {
      fetchEmailHistory();
    } else if (activeTab === 'templates') {
      fetchTemplates();
    } else if (activeTab === 'lists') {
      fetchRecipientLists();
      fetchClients();
    }
  }, [activeTab]);

  // Fetch clients for compose modal
  useEffect(() => {
    if (isComposeOpen && clients.length === 0) {
      fetchClients();
    }
  }, [isComposeOpen]);

  const fetchEmailHistory = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('api/v1/email/history/?page=1&page_size=50');
      setEmailHistory(response.data.results || []);
    } catch (err) {
      setError('Σφάλμα φόρτωσης ιστορικού');
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('api/v1/email/templates/');
      setTemplates(response.data || []);
    } catch (err) {
      setError('Σφάλμα φόρτωσης προτύπων');
    } finally {
      setLoading(false);
    }
  };

  const fetchRecipientLists = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('api/v1/email/recipient-lists/');
      setRecipientLists(response.data || []);
    } catch (err) {
      setError('Σφάλμα φόρτωσης λιστών');
    } finally {
      setLoading(false);
    }
  };

  const fetchClients = async () => {
    try {
      const response = await apiClient.get('api/v1/clients/?page_size=1000');
      setClients(response.data.results || []);
    } catch (err) {
      console.error('Error fetching clients:', err);
    }
  };

  // Send email
  const handleSendEmail = async () => {
    if (!composeForm.subject.trim() || !composeForm.body.trim()) {
      setError('Συμπληρώστε θέμα και μήνυμα');
      return;
    }

    setSending(true);
    try {
      if (composeForm.recipientType === 'client') {
        if (!composeForm.clientId) {
          setError('Επιλέξτε πελάτη');
          return;
        }
        await apiClient.post('api/v1/email/send/', {
          client_id: Number(composeForm.clientId),
          subject: composeForm.subject,
          body: composeForm.body,
          template_id: composeForm.templateId ? Number(composeForm.templateId) : null,
        });
      } else {
        if (!composeForm.listId) {
          setError('Επιλέξτε λίστα');
          return;
        }
        await apiClient.post('api/v1/email/send-to-list/', {
          list_id: Number(composeForm.listId),
          subject: composeForm.subject,
          body: composeForm.body,
          template_id: composeForm.templateId ? Number(composeForm.templateId) : null,
        });
      }

      setIsComposeOpen(false);
      resetComposeForm();
      fetchEmailHistory();
      setActiveTab('history');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Σφάλμα αποστολής email';
      setError(errorMessage);
    } finally {
      setSending(false);
    }
  };

  const resetComposeForm = () => {
    setComposeForm({
      recipientType: 'client',
      clientId: '',
      listId: '',
      templateId: '',
      subject: '',
      body: '',
    });
  };

  // Template selection fills subject/body
  const handleTemplateSelect = async (templateId: string) => {
    setComposeForm((prev) => ({ ...prev, templateId }));
    if (templateId) {
      const template = templates.find((t) => t.id === Number(templateId));
      if (template) {
        setComposeForm((prev) => ({
          ...prev,
          subject: template.subject,
          body: template.body_html,
        }));
      }
    }
  };

  // Save recipient list
  const handleSaveList = async () => {
    if (!listForm.name.trim()) {
      setError('Εισάγετε όνομα λίστας');
      return;
    }

    try {
      if (editingList) {
        await apiClient.put(`api/v1/email/recipient-lists/${editingList.id}/`, {
          name: listForm.name,
          description: listForm.description,
          requires_approval: listForm.requires_approval,
          client_ids: listForm.selectedClients,
        });
      } else {
        await apiClient.post('api/v1/email/recipient-lists/', {
          name: listForm.name,
          description: listForm.description,
          requires_approval: listForm.requires_approval,
          client_ids: listForm.selectedClients,
        });
      }

      setIsListModalOpen(false);
      resetListForm();
      fetchRecipientLists();
    } catch (err) {
      setError('Σφάλμα αποθήκευσης λίστας');
    }
  };

  const resetListForm = () => {
    setListForm({
      name: '',
      description: '',
      requires_approval: true,
      selectedClients: [],
    });
    setEditingList(null);
  };

  const handleEditList = (list: RecipientList) => {
    setEditingList(list);
    setListForm({
      name: list.name,
      description: list.description,
      requires_approval: list.requires_approval,
      selectedClients: list.clients_data.map((c) => c.id),
    });
    setIsListModalOpen(true);
  };

  const handleDeleteList = async (listId: number) => {
    if (!window.confirm('Είστε σίγουροι ότι θέλετε να διαγράψετε αυτή τη λίστα;')) {
      return;
    }

    try {
      await apiClient.delete(`api/v1/email/recipient-lists/${listId}/`);
      fetchRecipientLists();
    } catch (err) {
      setError('Σφάλμα διαγραφής λίστας');
    }
  };

  const toggleClientInList = (clientId: number) => {
    setListForm((prev) => ({
      ...prev,
      selectedClients: prev.selectedClients.includes(clientId)
        ? prev.selectedClients.filter((id) => id !== clientId)
        : [...prev.selectedClients, clientId],
    }));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'sent':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'pending':
      case 'queued':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      default:
        return <Mail className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Αλληλογραφία</h1>
          <p className="text-gray-500 mt-1">Διαχείριση email, προτύπων και λιστών παραληπτών</p>
        </div>
        <Button onClick={() => setIsComposeOpen(true)}>
          <Plus size={18} className="mr-2" />
          Νέο Email
        </Button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
          <span className="text-red-700">{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            <XCircle size={20} />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          <button
            onClick={() => setActiveTab('history')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'history'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Send className="w-4 h-4 inline-block mr-2" />
            Ιστορικό
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'templates'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <FileText className="w-4 h-4 inline-block mr-2" />
            Πρότυπα
          </button>
          <button
            onClick={() => setActiveTab('lists')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'lists'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Users className="w-4 h-4 inline-block mr-2" />
            Λίστες Παραληπτών
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg border border-gray-200">
        {loading ? (
          <div className="p-12 text-center">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin mx-auto mb-4" />
            <p className="text-gray-500">Φόρτωση...</p>
          </div>
        ) : (
          <>
            {/* History Tab */}
            {activeTab === 'history' && (
              <div>
                {emailHistory.length === 0 ? (
                  <div className="p-12 text-center">
                    <Mail className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Δεν υπάρχει ιστορικό email</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {emailHistory.map((email) => (
                      <div key={email.id} className="p-4 hover:bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {getStatusIcon(email.status)}
                            <div>
                              <p className="font-medium text-gray-900">{email.subject}</p>
                              <p className="text-sm text-gray-500">
                                Προς: {email.recipient_name || email.recipient_email}
                                {email.client_name && ` (${email.client_name})`}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-sm text-gray-500">
                              {new Date(email.sent_at).toLocaleString('el-GR')}
                            </p>
                            {email.sent_by_name && (
                              <p className="text-xs text-gray-400">από {email.sent_by_name}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Templates Tab */}
            {activeTab === 'templates' && (
              <div className="p-6">
                {templates.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Δεν υπάρχουν πρότυπα</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {templates.map((template) => (
                      <div
                        key={template.id}
                        className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-gray-900">{template.name}</h4>
                          {template.requires_approval && (
                            <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                              Έγκριση
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-500 mb-2">{template.description}</p>
                        <p className="text-xs text-gray-400 truncate">Θέμα: {template.subject}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Lists Tab */}
            {activeTab === 'lists' && (
              <div className="p-6">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-lg font-semibold text-gray-900">Λίστες Παραληπτών</h3>
                  <Button
                    onClick={() => {
                      resetListForm();
                      setIsListModalOpen(true);
                    }}
                    size="sm"
                  >
                    <Plus size={16} className="mr-1" />
                    Νέα Λίστα
                  </Button>
                </div>

                {recipientLists.length === 0 ? (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500 mb-4">Δεν υπάρχουν λίστες παραληπτών</p>
                    <Button
                      onClick={() => {
                        resetListForm();
                        setIsListModalOpen(true);
                      }}
                    >
                      <Plus size={18} className="mr-2" />
                      Δημιουργία Λίστας
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {recipientLists.map((list) => (
                      <div
                        key={list.id}
                        className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium text-gray-900">{list.name}</h4>
                              {list.requires_approval && (
                                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                                  Έγκριση
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-500">{list.description}</p>
                            <p className="text-xs text-gray-400 mt-1">
                              {list.client_count} πελάτες • {list.email_count} με email
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleEditList(list)}
                            >
                              <Edit2 size={14} />
                            </Button>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleDeleteList(list.id)}
                            >
                              <Trash2 size={14} className="text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Compose Email Modal */}
      <Modal
        isOpen={isComposeOpen}
        onClose={() => {
          setIsComposeOpen(false);
          resetComposeForm();
        }}
        title="Νέο Email"
        size="xl"
      >
        <div className="space-y-4">
          {/* Recipient Type Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Αποστολή σε</label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="recipientType"
                  value="client"
                  checked={composeForm.recipientType === 'client'}
                  onChange={() => setComposeForm((prev) => ({ ...prev, recipientType: 'client' }))}
                  className="mr-2"
                />
                Πελάτη
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="recipientType"
                  value="list"
                  checked={composeForm.recipientType === 'list'}
                  onChange={() => setComposeForm((prev) => ({ ...prev, recipientType: 'list' }))}
                  className="mr-2"
                />
                Λίστα Παραληπτών
              </label>
            </div>
          </div>

          {/* Client/List Selection */}
          {composeForm.recipientType === 'client' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Πελάτης</label>
              <select
                value={composeForm.clientId}
                onChange={(e) => setComposeForm((prev) => ({ ...prev, clientId: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- Επιλέξτε πελάτη --</option>
                {clients
                  .filter((c) => c.email)
                  .map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.eponimia || client.onoma} ({client.email})
                    </option>
                  ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Λίστα</label>
              <select
                value={composeForm.listId}
                onChange={(e) => setComposeForm((prev) => ({ ...prev, listId: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- Επιλέξτε λίστα --</option>
                {recipientLists.map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.name} ({list.email_count} παραλήπτες)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Template Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Πρότυπο</label>
            <select
              value={composeForm.templateId}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">-- Χωρίς πρότυπο --</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>

          {/* Subject */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Θέμα</label>
            <input
              type="text"
              value={composeForm.subject}
              onChange={(e) => setComposeForm((prev) => ({ ...prev, subject: e.target.value }))}
              placeholder="Θέμα email..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Body */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Μήνυμα</label>
            <textarea
              value={composeForm.body}
              onChange={(e) => setComposeForm((prev) => ({ ...prev, body: e.target.value }))}
              placeholder="Κείμενο email..."
              rows={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            />
            <p className="text-xs text-gray-400 mt-1">
              Διαθέσιμες μεταβλητές: {'{client_name}'}, {'{client_afm}'}, {'{client_email}'}
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => {
                setIsComposeOpen(false);
                resetComposeForm();
              }}
            >
              Ακύρωση
            </Button>
            <Button
              onClick={handleSendEmail}
              disabled={sending || !composeForm.subject.trim() || !composeForm.body.trim()}
              isLoading={sending}
              className="flex-1"
            >
              <Send className="w-4 h-4 mr-2" />
              Αποστολή
            </Button>
          </div>
        </div>
      </Modal>

      {/* Create/Edit List Modal */}
      <Modal
        isOpen={isListModalOpen}
        onClose={() => {
          setIsListModalOpen(false);
          resetListForm();
        }}
        title={editingList ? 'Επεξεργασία Λίστας' : 'Νέα Λίστα Παραληπτών'}
        size="xl"
      >
        <div className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Όνομα Λίστας</label>
            <input
              type="text"
              value={listForm.name}
              onChange={(e) => setListForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="π.χ. Πελάτες Μηνιαίο ΦΠΑ"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Περιγραφή</label>
            <input
              type="text"
              value={listForm.description}
              onChange={(e) => setListForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Προαιρετική περιγραφή..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Requires Approval */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="requires_approval"
              checked={listForm.requires_approval}
              onChange={(e) =>
                setListForm((prev) => ({ ...prev, requires_approval: e.target.checked }))
              }
              className="w-4 h-4 text-blue-600 rounded mr-2"
            />
            <label htmlFor="requires_approval" className="text-sm text-gray-700">
              Απαιτεί έγκριση πριν την αποστολή
            </label>
          </div>

          {/* Client Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Πελάτες ({listForm.selectedClients.length} επιλεγμένοι)
            </label>
            <div className="border border-gray-200 rounded-md max-h-64 overflow-y-auto">
              {clients
                .filter((c) => c.email)
                .map((client) => (
                  <label
                    key={client.id}
                    className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={listForm.selectedClients.includes(client.id)}
                      onChange={() => toggleClientInList(client.id)}
                      className="w-4 h-4 text-blue-600 rounded mr-3"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {client.eponimia || client.onoma}
                      </p>
                      <p className="text-xs text-gray-500">{client.email}</p>
                    </div>
                  </label>
                ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => {
                setIsListModalOpen(false);
                resetListForm();
              }}
            >
              Ακύρωση
            </Button>
            <Button onClick={handleSaveList} disabled={!listForm.name.trim()} className="flex-1">
              {editingList ? 'Αποθήκευση' : 'Δημιουργία'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
