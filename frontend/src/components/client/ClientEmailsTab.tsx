import { useState } from 'react';
import { RefreshCw, Plus, Send, CheckCircle, XCircle, Clock, Mail } from 'lucide-react';
import { Button } from '../Button';
import { Modal } from '../Modal';
import apiClient from '../../api/client';

// Email interface
export interface EmailItem {
  id: number;
  recipient_email: string;
  subject: string;
  status: string;
  status_display?: string;
  sent_at: string | null;
  template_name?: string | null;
}

interface EmailTemplate {
  id: number;
  name: string;
  subject: string;
  body_html: string;
}

// Props interface
export interface ClientEmailsTabProps {
  data: { emails: EmailItem[] } | undefined;
  isLoading: boolean;
  clientId: number;
  clientName: string;
  clientEmail: string;
  onRefresh?: () => void;
}

export default function ClientEmailsTab({
  data,
  isLoading,
  clientId,
  clientName,
  clientEmail,
  onRefresh,
}: ClientEmailsTabProps) {
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [composeForm, setComposeForm] = useState({
    templateId: '',
    subject: '',
    body: '',
  });

  const fetchTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const response = await apiClient.get('/v1/email/templates/');
      setTemplates(response.data || []);
    } catch (err) {
      console.error('Error fetching templates:', err);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const handleOpenCompose = () => {
    if (templates.length === 0) {
      fetchTemplates();
    }
    setIsComposeOpen(true);
  };

  const handleTemplateSelect = (templateId: string) => {
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

  const handleSendEmail = async () => {
    if (!composeForm.subject.trim() || !composeForm.body.trim()) {
      setError('Συμπληρώστε θέμα και μήνυμα');
      return;
    }

    setSending(true);
    setError(null);
    try {
      await apiClient.post('/v1/email/send/', {
        client_id: clientId,
        subject: composeForm.subject,
        body: composeForm.body,
        template_id: composeForm.templateId ? Number(composeForm.templateId) : null,
      });

      setIsComposeOpen(false);
      setComposeForm({ templateId: '', subject: '', body: '' });
      if (onRefresh) {
        onRefresh();
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Σφάλμα αποστολής email';
      setError(errorMessage);
    } finally {
      setSending(false);
    }
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
    <div className="space-y-4">
      {/* Header with New Email button */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Email</h3>
        {clientEmail && (
          <Button size="sm" onClick={handleOpenCompose}>
            <Plus size={16} className="mr-1" />
            Νέο Email
          </Button>
        )}
      </div>

      {/* No email warning */}
      {!clientEmail && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-700">
          Ο πελάτης δεν έχει καταχωρημένο email
        </div>
      )}

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
                  Ημερομηνία
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Θέμα
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Παραλήπτης
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Κατάσταση
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.emails.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    Δεν υπάρχουν καταγεγραμμένα email
                  </td>
                </tr>
              ) : (
                data.emails.map((email) => (
                  <tr key={email.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {email.sent_at
                        ? new Date(email.sent_at).toLocaleString('el-GR')
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(email.status)}
                        {email.subject}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{email.recipient_email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          email.status === 'sent'
                            ? 'bg-green-100 text-green-800'
                            : email.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {email.status_display || email.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Compose Email Modal */}
      <Modal
        isOpen={isComposeOpen}
        onClose={() => {
          setIsComposeOpen(false);
          setComposeForm({ templateId: '', subject: '', body: '' });
          setError(null);
        }}
        title="Νέο Email"
        size="xl"
      >
        <div className="space-y-4">
          {/* Recipient info */}
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm">
              <span className="text-gray-500">Προς:</span>{' '}
              <span className="font-medium">{clientName}</span>{' '}
              <span className="text-gray-500">({clientEmail})</span>
            </p>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
              <span className="text-sm text-red-700">{error}</span>
            </div>
          )}

          {/* Template Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Πρότυπο</label>
            <select
              value={composeForm.templateId}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loadingTemplates}
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
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <Button
              variant="secondary"
              onClick={() => {
                setIsComposeOpen(false);
                setComposeForm({ templateId: '', subject: '', body: '' });
                setError(null);
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
    </div>
  );
}
