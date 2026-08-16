/**
 * CompleteObligationModal.tsx
 * Modal for completing an obligation with optional document attachment and email notification
 * Features: Drag & drop file upload, save to client folder, send email with attachment
 */

import { useState, useRef, useCallback } from 'react';
import { CheckCircle, Upload, File, X, AlertCircle, Mail, FolderPlus, Paperclip } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { useEmailTemplates } from '../hooks/useEmail';
import type { Obligation, EmailTemplate, ClientDocument } from '../types';

interface CompleteObligationModalProps {
  isOpen: boolean;
  onClose: () => void;
  obligation: Obligation | null;
  clientName: string;
  clientEmail?: string;
  existingDocuments?: ClientDocument[];
  onComplete: (data: {
    file?: File | null;
    documentId?: number | null;
    saveToClientFolder: boolean;
    sendEmail: boolean;
    attachToEmail: boolean;
    emailTemplateId?: number | null;
    notes: string;
    timeSpent?: number | null;
  }) => Promise<void>;
  isLoading?: boolean;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'];
const MAX_FILE_SIZE = 10 * 1024 * 1024;

export function CompleteObligationModal({
  isOpen,
  onClose,
  obligation,
  clientName,
  clientEmail,
  existingDocuments = [],
  onComplete,
  isLoading = false,
}: CompleteObligationModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [documentSource, setDocumentSource] = useState<'upload' | 'existing'>('upload');
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [saveToClientFolder, setSaveToClientFolder] = useState(true);
  const [sendEmail, setSendEmail] = useState(false);
  const [attachToEmail, setAttachToEmail] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [timeSpent, setTimeSpent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: templates } = useEmailTemplates();

  const validateFile = useCallback((file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Μη επιτρεπτός τύπος αρχείου. Επιτρέπονται: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'Το αρχείο είναι μεγαλύτερο από 10MB.';
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (selectedFile: File) => {
      const validationError = validateFile(selectedFile);
      if (validationError) {
        setError(validationError);
        return;
      }
      setFile(selectedFile);
      setSelectedDocId(null);
      setDocumentSource('upload');
      setError(null);
    },
    [validateFile]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFileSelect(selectedFile);
      }
    },
    [handleFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleSubmit = async () => {
    try {
      await onComplete({
        file: documentSource === 'upload' ? file : null,
        documentId: documentSource === 'existing' ? selectedDocId : null,
        saveToClientFolder,
        sendEmail: sendEmail && !!clientEmail,
        attachToEmail: sendEmail && attachToEmail && (!!file || !!selectedDocId),
        emailTemplateId: sendEmail && selectedTemplate ? selectedTemplate : null,
        notes,
        timeSpent: timeSpent ? parseFloat(timeSpent) : null,
      });
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Σφάλμα κατά την ολοκλήρωση');
    }
  };

  const handleClose = () => {
    setFile(null);
    setDocumentSource('upload');
    setSelectedDocId(null);
    setSaveToClientFolder(true);
    setSendEmail(false);
    setAttachToEmail(false);
    setSelectedTemplate(null);
    setNotes('');
    setTimeSpent('');
    setError(null);
    setIsDragging(false);
    onClose();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const hasDocument = file || selectedDocId;

  if (!obligation) return null;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Ολοκλήρωση Υποχρέωσης" size="lg">
      <div className="space-y-4">
        {/* Obligation info */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-8 h-8 text-green-500" />
            <div>
              <p className="font-medium text-gray-900">
                {obligation.type_name || obligation.type_code}
              </p>
              <p className="text-sm text-gray-500">
                {clientName} - {String(obligation.month).padStart(2, '0')}/{obligation.year}
              </p>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-sm text-red-700">{error}</span>
          </div>
        )}

        {/* Document attachment section */}
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Paperclip className="w-4 h-4 text-gray-500" />
            <span className="font-medium text-gray-900">Επισύναψη Εγγράφου</span>
          </div>

          {/* Drop zone: είναι ΟΝΤΩΣ διαδραστικό (ανοίγει τον file picker),
              οπότε χρειάζεται role, εστίαση και πληκτρολόγιο — αλλιώς ο
              χρήστης χωρίς ποντίκι δεν μπορεί καθόλου να ανεβάσει αρχείο. */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Επιλογή αρχείου για ανέβασμα"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            className={`
              border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
              focus:outline-none focus:ring-2 focus:ring-blue-500
              ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleInputChange}
              accept={ALLOWED_EXTENSIONS.join(',')}
              className="hidden"
            />
            <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
            <p className="text-gray-600 text-sm font-medium">
              Σύρετε αρχείο εδώ ή κάντε κλικ για επιλογή
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF, DOC, XLS, JPG, PNG (max 10MB)
            </p>
          </div>

          {/* Selected file preview */}
          {file && (
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg mt-3 border border-green-200">
              <File className="w-6 h-6 text-green-600" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-green-800 truncate">{file.name}</p>
                <p className="text-xs text-green-600">{formatFileSize(file.size)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="p-1 hover:bg-green-100 rounded"
              >
                <X className="w-4 h-4 text-green-600" />
              </button>
            </div>
          )}

          {/* Existing document selection */}
          {existingDocuments.length > 0 && !file && (
            <div className="mt-3">
              <label className="block text-sm text-gray-600 mb-1">
                Ή επιλέξτε υπάρχον έγγραφο:
              </label>
              <select
                value={selectedDocId || ''}
                onChange={(e) => {
                  setSelectedDocId(e.target.value ? Number(e.target.value) : null);
                  setDocumentSource('existing');
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">-- Επιλέξτε έγγραφο --</option>
                {existingDocuments.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Save to client folder option */}
        {hasDocument && (
          <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="checkbox"
              checked={saveToClientFolder}
              onChange={(e) => setSaveToClientFolder(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <FolderPlus className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-700">Αποθήκευση στον φάκελο πελάτη</span>
          </label>
        )}

        {/* Send email option */}
        <div className="border border-gray-200 rounded-lg p-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => {
                setSendEmail(e.target.checked);
                if (!e.target.checked) {
                  setAttachToEmail(false);
                }
              }}
              disabled={!clientEmail}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <Mail className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-gray-900">Αποστολή email στον πελάτη</span>
            {!clientEmail && (
              <span className="text-xs text-gray-400">(ο πελάτης δεν έχει email)</span>
            )}
          </label>

          {sendEmail && clientEmail && (
            <div className="mt-4 pl-6 space-y-3">
              {/* Attach document to email option */}
              {hasDocument && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={attachToEmail}
                    onChange={(e) => setAttachToEmail(e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <Paperclip className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-700">Επισύναψη εγγράφου στο email</span>
                </label>
              )}

              {/* Template selection */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">Πρότυπο</label>
                <select
                  value={selectedTemplate || ''}
                  onChange={(e) =>
                    setSelectedTemplate(e.target.value ? Number(e.target.value) : null)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="">Αυτόματη επιλογή</option>
                  {templates?.map((template: EmailTemplate) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Σημειώσεις
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Προαιρετικές σημειώσεις..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm resize-y"
          />
        </div>

        {/* Time spent */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Χρόνος εργασίας (ώρες)
          </label>
          <input
            type="number"
            value={timeSpent}
            onChange={(e) => setTimeSpent(e.target.value)}
            placeholder="π.χ. 1.5"
            step="0.25"
            min="0"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
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
            Ολοκλήρωση
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default CompleteObligationModal;
