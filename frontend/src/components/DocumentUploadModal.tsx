/**
 * DocumentUploadModal.tsx
 * Modal for uploading documents with drag & drop and versioning support
 */

import { useState, useCallback, useRef } from 'react';
import { Upload, File, X, AlertCircle, Loader2 } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { VersionConfirmDialog, type ExistingDocument, type VersionAction } from './VersionConfirmDialog';
import { DOCUMENT_CATEGORY_LABELS } from '../types';
import {
  checkExistingDocument,
  useUploadDocumentWithVersion,
  type ExistingDocumentInfo,
} from '../hooks/useDocuments';

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (data: {
    file: File;
    category: string;
    description: string;
    sendEmail: boolean;
  }) => Promise<void>;
  clientId?: number;
  clientName?: string;
  obligationId?: number;
  obligationType?: string;
  isLoading?: boolean;
  // Enable versioning support
  enableVersioning?: boolean;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function DocumentUploadModal({
  isOpen,
  onClose,
  onUpload,
  clientId,
  clientName,
  obligationId,
  obligationType,
  isLoading = false,
  enableVersioning = false,
}: DocumentUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState('general');
  const [description, setDescription] = useState('');
  const [sendEmail, setSendEmail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isCheckingExisting, setIsCheckingExisting] = useState(false);
  const [showVersionDialog, setShowVersionDialog] = useState(false);
  const [existingDoc, setExistingDoc] = useState<ExistingDocument | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadWithVersion = useUploadDocumentWithVersion();

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
      setError(null);
    },
    [validateFile]
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

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFileSelect(selectedFile);
      }
    },
    [handleFileSelect]
  );

  const handleSubmit = async () => {
    if (!file) return;

    // If versioning is enabled and we have clientId, check for existing
    if (enableVersioning && clientId) {
      setIsCheckingExisting(true);
      try {
        const result: ExistingDocumentInfo = await checkExistingDocument({
          client_id: clientId,
          obligation_id: obligationId,
          category: category !== 'general' ? category : undefined,
        });

        if (result.exists && result.document) {
          // Show version dialog
          setExistingDoc({
            id: result.document.id,
            filename: result.document.filename,
            original_filename: result.document.original_filename,
            version: result.document.version,
            file_size: result.document.file_size,
            file_size_display: result.document.file_size_display,
            uploaded_at: result.document.uploaded_at,
            uploaded_by: result.document.uploaded_by,
            url: result.document.url,
          });
          setShowVersionDialog(true);
          setIsCheckingExisting(false);
          return;
        }
      } catch (err) {
        // If check fails, proceed with normal upload
        console.warn('Could not check for existing document:', err);
      }
      setIsCheckingExisting(false);
    }

    // Proceed with upload
    await performUpload();
  };

  const performUpload = async (versionAction?: VersionAction) => {
    if (!file) return;

    try {
      if (enableVersioning && clientId) {
        // Use versioned upload
        const result = await uploadWithVersion.mutateAsync({
          file,
          client_id: clientId,
          obligation_id: obligationId,
          category,
          description,
          version_action: versionAction || 'auto',
        });

        if (result.success) {
          handleClose();
        } else {
          setError(result.error || 'Σφάλμα κατά τη μεταφόρτωση');
        }
      } else {
        // Use original upload callback
        await onUpload({ file, category, description, sendEmail });
        handleClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Σφάλμα κατά τη μεταφόρτωση');
    }
  };

  const handleVersionConfirm = async (action: VersionAction) => {
    setShowVersionDialog(false);
    await performUpload(action);
  };

  const handleClose = () => {
    setFile(null);
    setCategory('general');
    setDescription('');
    setSendEmail(false);
    setError(null);
    setExistingDoc(null);
    setShowVersionDialog(false);
    onClose();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const isUploading = isLoading || uploadWithVersion.isPending || isCheckingExisting;

  return (
    <>
      <Modal isOpen={isOpen && !showVersionDialog} onClose={handleClose} title="Επισύναψη Εγγράφου" size="lg">
        <div className="space-y-4">
          {/* Client/Obligation info */}
          {(clientName || obligationType) && (
            <div className="bg-gray-50 rounded-lg p-3 text-sm">
              {clientName && (
                <p>
                  <span className="text-gray-500">Πελάτης:</span>{' '}
                  <span className="font-medium">{clientName}</span>
                </p>
              )}
              {obligationType && (
                <p>
                  <span className="text-gray-500">Υποχρέωση:</span>{' '}
                  <span className="font-medium">{obligationType}</span>
                </p>
              )}
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
              <span className="text-sm text-red-700">{error}</span>
            </div>
          )}

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
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
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
            <Upload className="w-10 h-10 mx-auto text-gray-400 mb-3" />
            <p className="text-gray-600 font-medium">
              Σύρετε αρχείο εδώ ή κάντε κλικ για επιλογή
            </p>
            <p className="text-sm text-gray-400 mt-1">
              PDF, DOC, XLS, JPG, PNG (max 10MB)
            </p>
          </div>

          {/* Selected file preview */}
          {file && (
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <File className="w-8 h-8 text-blue-500" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{file.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="p-1 hover:bg-gray-200 rounded"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
          )}

          {/* Category selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Τύπος εγγράφου
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(DOCUMENT_CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Περιγραφή (προαιρετικό)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Σύντομη περιγραφή του εγγράφου..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Send email option */}
          {!enableVersioning && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={sendEmail}
                onChange={(e) => setSendEmail(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded"
              />
              <span className="text-sm text-gray-700">Αποστολή email στον πελάτη</span>
            </label>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={handleClose} disabled={isUploading}>
              Ακύρωση
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!file || isUploading}
              className="flex-1"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {isCheckingExisting ? 'Έλεγχος...' : 'Μεταφόρτωση...'}
                </>
              ) : (
                'Επισύναψη'
              )}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Version Confirmation Dialog */}
      <VersionConfirmDialog
        isOpen={showVersionDialog}
        onClose={() => {
          setShowVersionDialog(false);
          setExistingDoc(null);
        }}
        onConfirm={handleVersionConfirm}
        existingDocument={existingDoc}
        newFileName={file?.name || ''}
        isLoading={uploadWithVersion.isPending}
      />
    </>
  );
}

export default DocumentUploadModal;
