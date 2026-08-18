/**
 * BulkCompleteModal.tsx
 * Modal for bulk completing obligations with individual document attachments
 * Features: Individual file upload per obligation, save to client folders, send emails with attachments
 */

import { useState, useRef, useCallback } from 'react';
import { CheckCircle, File, X, AlertCircle, Mail, FolderPlus, Paperclip, Plus, FileText } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { useEmailTemplates } from '../hooks/useEmail';
import type { Obligation } from '../types';

interface BulkCompleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  obligations: Obligation[];
  onComplete: (data: {
    obligationIds: number[];
    obligationFiles: { [key: number]: File | null };
    saveToClientFolders: boolean;
    sendEmails: boolean;
    attachToEmails: boolean;
    templateId?: number | null;
  }) => Promise<void>;
  isLoading?: boolean;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'];
const MAX_FILE_SIZE = 10 * 1024 * 1024;

export function BulkCompleteModal({
  isOpen,
  onClose,
  obligations,
  onComplete,
  isLoading = false,
}: BulkCompleteModalProps) {
  const [obligationFiles, setObligationFiles] = useState<{ [key: number]: File | null }>({});
  const [saveToClientFolders, setSaveToClientFolders] = useState(true);
  const [sendEmails, setSendEmails] = useState(false);
  const [attachToEmails, setAttachToEmails] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRefs = useRef<{ [key: number]: HTMLInputElement | null }>({});

  // Fetch email templates
  const { data: templates } = useEmailTemplates();

  const validateFile = useCallback((file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Μη επιτρεπτός τύπος αρχείου: ${file.name}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `Το αρχείο ${file.name} είναι μεγαλύτερο από 10MB.`;
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (obligationId: number, file: File | null) => {
      if (file) {
        const validationError = validateFile(file);
        if (validationError) {
          setError(validationError);
          return;
        }
      }
      setObligationFiles((prev) => ({
        ...prev,
        [obligationId]: file,
      }));
      setError(null);
    },
    [validateFile]
  );

  const handleInputChange = useCallback(
    (obligationId: number) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      handleFileSelect(obligationId, selectedFile || null);
    },
    [handleFileSelect]
  );

  const handleSubmit = async () => {
    try {
      // Pass ALL obligation IDs, not just those with files
      const obligationIds = obligations.map((o) => o.id);
      await onComplete({
        obligationIds,
        obligationFiles,
        saveToClientFolders,
        sendEmails,
        attachToEmails,
        templateId: sendEmails ? selectedTemplateId : null,
      });
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Σφάλμα κατά την ολοκλήρωση');
    }
  };

  const handleClose = () => {
    setObligationFiles({});
    setSaveToClientFolders(true);
    setSendEmails(false);
    setAttachToEmails(false);
    setSelectedTemplateId(null);
    setError(null);
    onClose();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const hasAnyFiles = Object.values(obligationFiles).some((f) => f !== null);
  const filesCount = Object.values(obligationFiles).filter((f) => f !== null).length;

  if (obligations.length === 0) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Μαζική Ολοκλήρωση (${obligations.length} υποχρεώσεις)`}
      size="xl"
    >
      <div className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        {/* Obligations list with file upload */}
        <div className="max-h-80 overflow-y-auto space-y-3 pr-1">
          {obligations.map((obligation, index) => {
            const file = obligationFiles[obligation.id];
            return (
              <div
                key={obligation.id}
                className="border border-gray-200 rounded-lg p-3 bg-white"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-xs font-medium flex items-center justify-center">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate">
                        {obligation.type_name || obligation.type_code} - {obligation.client_name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {String(obligation.month).padStart(2, '0')}/{obligation.year}
                      </p>
                    </div>
                  </div>

                  {/* File upload button or file preview */}
                  <div className="flex-shrink-0">
                    <input
                      ref={(el) => {
                        fileInputRefs.current[obligation.id] = el;
                      }}
                      type="file"
                      onChange={handleInputChange(obligation.id)}
                      accept={ALLOWED_EXTENSIONS.join(',')}
                      className="hidden"
                    />

                    {file ? (
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 rounded-lg border border-green-200">
                        <File className="w-4 h-4 text-green-600" />
                        <div className="max-w-32 min-w-0">
                          <p className="text-xs font-medium text-green-800 truncate">
                            {file.name}
                          </p>
                          <p className="text-xs text-green-600">{formatFileSize(file.size)}</p>
                        </div>
                        <button
                          onClick={() => handleFileSelect(obligation.id, null)}
                          className="p-0.5 hover:bg-green-100 rounded"
                        >
                          <X className="w-3 h-3 text-green-600" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => fileInputRefs.current[obligation.id]?.click()}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:border-gray-400 hover:bg-gray-50 transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                        Επιλογή αρχείου
                      </button>
                    )}
                  </div>
                </div>

                {!file && (
                  <p className="text-xs text-gray-400 mt-2 ml-9">(χωρίς αρχείο)</p>
                )}
              </div>
            );
          })}
        </div>

        {/* Summary */}
        {filesCount > 0 && (
          <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-700">
            <strong>{filesCount}</strong> από {obligations.length} υποχρεώσεις έχουν επισυναπτόμενο αρχείο
          </div>
        )}

        {/* Save to client folders option */}
        {hasAnyFiles && (
          <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="checkbox"
              checked={saveToClientFolders}
              onChange={(e) => setSaveToClientFolders(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <FolderPlus className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-700">Αποθήκευση εγγράφων στους φακέλους πελατών</span>
          </label>
        )}

        {/* Send emails option */}
        <div className="border border-gray-200 rounded-lg p-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={sendEmails}
              onChange={(e) => {
                setSendEmails(e.target.checked);
                if (!e.target.checked) {
                  setAttachToEmails(false);
                }
              }}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <Mail className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-gray-900">Αποστολή email ενημέρωσης</span>
          </label>

          {sendEmails && (
            <div className="mt-3 pl-6 space-y-3">
              {/* Template selection */}
              <div>
                <label htmlFor="bulk-complete-modal-f1" className="flex items-center gap-2 text-sm text-gray-700 mb-1">
                  <FileText className="w-4 h-4 text-gray-400" />
                  Πρότυπο Email
                </label>
                <select id="bulk-complete-modal-f1"
                  value={selectedTemplateId || ''}
                  onChange={(e) => setSelectedTemplateId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Αυτόματη επιλογή (βάσει τύπου υποχρέωσης)</option>
                  {templates?.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                      {template.obligation_type_name && ` (${template.obligation_type_name})`}
                    </option>
                  ))}
                </select>
              </div>

              {/* Attach to emails */}
              {hasAnyFiles && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={attachToEmails}
                    onChange={(e) => setAttachToEmails(e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <Paperclip className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-700">Επισύναψη εγγράφων στα emails</span>
                </label>
              )}
              <p className="text-xs text-gray-500">
                Θα σταλεί email μόνο σε πελάτες που έχουν διεύθυνση email.
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleSubmit}
            isLoading={isLoading}
            disabled={isLoading}
            className="flex-1"
          >
            <CheckCircle className="w-4 h-4 mr-2" />
            Ολοκλήρωση Όλων
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default BulkCompleteModal;
