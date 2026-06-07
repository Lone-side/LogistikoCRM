/**
 * VersionConfirmDialog.tsx
 * Dialog for confirming action when uploading a file that already exists
 */

import { useState } from 'react';
import { AlertCircle, FileText, GitBranch, Replace } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';

export interface ExistingDocument {
  id: number;
  filename: string;
  original_filename?: string;
  version: number;
  file_size?: number;
  file_size_display?: string;
  uploaded_at: string;
  uploaded_by?: string | null;
  url?: string | null;
}

export type VersionAction = 'new_version' | 'replace';

interface VersionConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (action: VersionAction) => void;
  existingDocument: ExistingDocument | null;
  newFileName: string;
  isLoading?: boolean;
}

export function VersionConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  existingDocument,
  newFileName,
  isLoading = false,
}: VersionConfirmDialogProps) {
  const [selectedAction, setSelectedAction] = useState<VersionAction>('new_version');

  const handleConfirm = () => {
    onConfirm(selectedAction);
  };

  if (!existingDocument) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="" size="md">
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-gray-200">
          <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-amber-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Υπάρχον Αρχείο</h3>
            <p className="text-sm text-gray-500">Βρέθηκε αρχείο με παρόμοια στοιχεία</p>
          </div>
        </div>

        {/* Existing file info */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <FileText className="w-10 h-10 text-brand-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900 truncate">
                {existingDocument.original_filename || existingDocument.filename}
              </p>
              <div className="mt-1 space-y-1 text-sm text-gray-500">
                <p>
                  <span className="font-medium">Έκδοση:</span>{' '}
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-brand-100 text-brand-800">
                    v{existingDocument.version}
                  </span>
                </p>
                {existingDocument.file_size_display && (
                  <p>
                    <span className="font-medium">Μέγεθος:</span> {existingDocument.file_size_display}
                  </p>
                )}
                <p>
                  <span className="font-medium">Ανέβηκε:</span> {existingDocument.uploaded_at}
                </p>
                {existingDocument.uploaded_by && (
                  <p>
                    <span className="font-medium">Από:</span> {existingDocument.uploaded_by}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* New file info */}
        <div className="text-sm text-gray-600">
          <span className="font-medium">Νέο αρχείο:</span>{' '}
          <span className="text-gray-900">{newFileName}</span>
        </div>

        {/* Question */}
        <p className="text-gray-700 font-medium">Τι θέλετε να κάνετε;</p>

        {/* Options */}
        <div className="space-y-3">
          <label
            className={`
              flex items-start gap-4 p-4 border-2 rounded-lg cursor-pointer transition-all
              ${selectedAction === 'new_version'
                ? 'border-brand-500 bg-brand-50'
                : 'border-gray-200 hover:border-gray-300'
              }
            `}
            onClick={() => setSelectedAction('new_version')}
          >
            <input
              type="radio"
              name="versionAction"
              value="new_version"
              checked={selectedAction === 'new_version'}
              onChange={() => setSelectedAction('new_version')}
              className="mt-1 w-4 h-4 text-brand-600"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-brand-600" />
                <span className="font-semibold text-gray-900">Δημιουργία νέας έκδοσης</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Κρατάει το παλιό αρχείο (v{existingDocument.version}) και δημιουργεί νέα έκδοση (v{existingDocument.version + 1})
              </p>
            </div>
          </label>

          <label
            className={`
              flex items-start gap-4 p-4 border-2 rounded-lg cursor-pointer transition-all
              ${selectedAction === 'replace'
                ? 'border-brand-500 bg-brand-50'
                : 'border-gray-200 hover:border-gray-300'
              }
            `}
            onClick={() => setSelectedAction('replace')}
          >
            <input
              type="radio"
              name="versionAction"
              value="replace"
              checked={selectedAction === 'replace'}
              onChange={() => setSelectedAction('replace')}
              className="mt-1 w-4 h-4 text-brand-600"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Replace className="w-5 h-5 text-amber-600" />
                <span className="font-semibold text-gray-900">Αντικατάσταση</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">
                Διαγράφει το παλιό αρχείο και το αντικαθιστά με το νέο
              </p>
            </div>
          </label>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-gray-200">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1"
          >
            Ακύρωση
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isLoading}
            isLoading={isLoading}
            className="flex-1"
          >
            Συνέχεια
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default VersionConfirmDialog;
