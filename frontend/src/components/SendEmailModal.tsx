/**
 * SendEmailModal.tsx
 * Modal for sending emails to clients with template support
 */

import { useState, useEffect } from 'react';
import { Send, Paperclip, X, AlertCircle } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { useEmailTemplates, usePreviewEmail } from '../hooks/useEmail';
import type { EmailTemplate, ClientDocument } from '../types';

interface SendEmailModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSend: (data: {
    subject: string;
    body: string;
    templateId?: number;
    attachmentIds: number[];
  }) => Promise<void>;
  clientName: string;
  clientEmail: string;
  obligationId?: number;
  availableDocuments?: ClientDocument[];
  isLoading?: boolean;
}

export function SendEmailModal({
  isOpen,
  onClose,
  onSend,
  clientName,
  clientEmail,
  obligationId,
  availableDocuments = [],
  isLoading = false,
}: SendEmailModalProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [selectedAttachments, setSelectedAttachments] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: templates, isLoading: templatesLoading } = useEmailTemplates();
  const { mutate: previewEmail } = usePreviewEmail();

  // Load template preview when selected
  useEffect(() => {
    if (selectedTemplate && isOpen) {
      previewEmail(
        {
          templateId: selectedTemplate,
          obligationId,
        },
        {
          onSuccess: (preview) => {
            setSubject(preview.subject);
            setBody(preview.body);
          },
          onError: (err) => {
            setError(err instanceof Error ? err.message : 'Σφάλμα φόρτωσης προτύπου');
          },
        }
      );
    }
  }, [selectedTemplate, obligationId, isOpen, previewEmail]);

  const handleTemplateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setSelectedTemplate(value ? Number(value) : null);
  };

  const toggleAttachment = (docId: number) => {
    setSelectedAttachments((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSubmit = async () => {
    if (!subject.trim() || !body.trim()) {
      setError('Συμπληρώστε το θέμα και το μήνυμα.');
      return;
    }

    try {
      await onSend({
        subject,
        body,
        templateId: selectedTemplate || undefined,
        attachmentIds: selectedAttachments,
      });
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Σφάλμα αποστολής email');
    }
  };

  const handleClose = () => {
    setSelectedTemplate(null);
    setSubject('');
    setBody('');
    setSelectedAttachments([]);
    setError(null);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Αποστολή Email" size="xl">
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
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        {/* Template selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Πρότυπο</label>
          <select
            value={selectedTemplate || ''}
            onChange={handleTemplateChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={templatesLoading}
          >
            <option value="">-- Επιλέξτε πρότυπο --</option>
            {templates?.map((template: EmailTemplate) => (
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
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Θέμα email..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Body */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Μήνυμα</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Κείμενο email..."
            rows={8}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
          />
        </div>

        {/* Attachments */}
        {availableDocuments.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Paperclip className="w-4 h-4 inline-block mr-1" />
              Συνημμένα
            </label>
            <div className="border border-gray-200 rounded-md max-h-40 overflow-y-auto">
              {availableDocuments.map((doc) => (
                <label
                  key={doc.id}
                  className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedAttachments.includes(doc.id)}
                    onChange={() => toggleAttachment(doc.id)}
                    className="w-4 h-4 text-blue-600 rounded mr-3"
                  />
                  <span className="text-sm truncate">{doc.filename}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Selected attachments preview */}
        {selectedAttachments.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {selectedAttachments.map((docId) => {
              const doc = availableDocuments.find((d) => d.id === docId);
              if (!doc) return null;
              return (
                <span
                  key={docId}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 text-sm rounded"
                >
                  <Paperclip className="w-3 h-3" />
                  {doc.filename}
                  <button
                    onClick={() => toggleAttachment(docId)}
                    className="ml-1 hover:text-blue-900"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!subject.trim() || !body.trim() || isLoading}
            isLoading={isLoading}
            className="flex-1"
          >
            <Send className="w-4 h-4 mr-2" />
            Αποστολή
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default SendEmailModal;
