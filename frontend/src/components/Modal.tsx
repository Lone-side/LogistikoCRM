import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

export function Modal({ isOpen, onClose, title, children, size = 'md' }: ModalProps) {
  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop — καθαρά οπτικό βοήθημα για ποντίκι. Κρύβεται από τον
          a11y tree: ο χρήστης πληκτρολογίου κλείνει με Escape (listener
          παραπάνω) ή με το κουμπί «Κλείσιμο», που έχει aria-label. */}
      <div
        aria-hidden="true"
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        {/* Χωρίς onClick stopPropagation: το backdrop είναι ΑΔΕΛΦΟΣ κόμβος,
            οπότε τα κλικ στον διάλογο δεν το έφταναν ποτέ — ο handler ήταν
            νεκρός κώδικας που έκανε τον διάλογο να μοιάζει διαδραστικός. */}
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className={`relative w-full ${sizeClasses[size]} bg-white rounded-lg shadow-xl transform transition-all`}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h3 id="modal-title" className="text-lg font-semibold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              aria-label="Κλείσιμο"
              className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4">{children}</div>
        </div>
      </div>
    </div>
  );
}

export default Modal;
