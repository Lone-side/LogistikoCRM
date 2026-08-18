import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isLoading?: boolean;
  isPending?: boolean;  // Alias for isLoading
  variant?: 'danger' | 'warning';
  /** Όταν οριστεί, ο χρήστης πρέπει να πληκτρολογήσει ακριβώς αυτή την τιμή
   *  για να ενεργοποιηθεί το κουμπί επιβεβαίωσης (π.χ. για μαζικές διαγραφές). */
  requireTypedConfirmation?: string;
  typedConfirmationLabel?: string;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Επιβεβαίωση',
  cancelText = 'Ακύρωση',
  isLoading = false,
  isPending,
  variant = 'danger',
  requireTypedConfirmation,
  typedConfirmationLabel,
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      {/* Το σώμα ζει ΜΕΣΑ στο Modal, που κάνει unmount όταν κλείνει.
          Έτσι το typedValue μηδενίζεται από μόνο του σε κάθε άνοιγμα,
          χωρίς effect που να πειράζει state. */}
      <ConfirmDialogBody
        onClose={onClose}
        onConfirm={onConfirm}
        message={message}
        confirmText={confirmText}
        cancelText={cancelText}
        loading={isPending ?? isLoading}
        variant={variant}
        requireTypedConfirmation={requireTypedConfirmation}
        typedConfirmationLabel={typedConfirmationLabel}
      />
    </Modal>
  );
}

type ConfirmDialogBodyProps = Omit<
  ConfirmDialogProps,
  'isOpen' | 'title' | 'isLoading' | 'isPending' | 'variant'
> & {
  loading: boolean;
  variant: 'danger' | 'warning';
};

function ConfirmDialogBody({
  onClose,
  onConfirm,
  message,
  confirmText,
  cancelText,
  loading,
  variant,
  requireTypedConfirmation,
  typedConfirmationLabel,
}: ConfirmDialogBodyProps) {
  const iconColor = variant === 'danger' ? 'text-red-600' : 'text-yellow-600';
  const iconBg = variant === 'danger' ? 'bg-red-100' : 'bg-yellow-100';

  const [typedValue, setTypedValue] = useState('');

  const confirmDisabled =
    loading || (requireTypedConfirmation !== undefined && typedValue !== requireTypedConfirmation);

  return (
    <div className="flex flex-col items-center text-center">
      <div className={`p-3 ${iconBg} rounded-full mb-4`}>
        <AlertTriangle className={`w-6 h-6 ${iconColor}`} />
      </div>
      <p className="text-gray-600 mb-6">{message}</p>
      {requireTypedConfirmation !== undefined && (
        <div className="w-full mb-6 text-left">
          <label htmlFor="confirm-dialog-f1" className="block text-sm font-medium text-gray-700 mb-1">
            {typedConfirmationLabel ?? `Πληκτρολόγησε "${requireTypedConfirmation}" για επιβεβαίωση`}
          </label>
          <input id="confirm-dialog-f1"
            type="text"
            value={typedValue}
            onChange={(e) => setTypedValue(e.target.value)}
            autoFocus
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            placeholder={requireTypedConfirmation}
          />
        </div>
      )}
      <div className="flex gap-3 w-full">
        <Button
          variant="secondary"
          onClick={onClose}
          disabled={loading}
          className="flex-1"
        >
          {cancelText}
        </Button>
        <Button
          variant="danger"
          onClick={onConfirm}
          isLoading={loading}
          disabled={confirmDisabled}
          className="flex-1"
        >
          {confirmText}
        </Button>
      </div>
    </div>
  );
}

export default ConfirmDialog;
