/**
 * FilePreviewModal.tsx
 * Modal for previewing PDF files and images
 */

import { useState } from 'react';
import { X, Download, ExternalLink, FileText, Image as ImageIcon, Loader2 } from 'lucide-react';
import { Modal } from './Modal';

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileUrl: string | null;
  fileName: string;
  fileType?: string;
}

export function FilePreviewModal({
  isOpen,
  onClose,
  fileUrl,
  fileName,
  fileType,
}: FilePreviewModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previousPreview, setPreviousPreview] = useState({ isOpen, fileUrl });

  if (previousPreview.isOpen !== isOpen || previousPreview.fileUrl !== fileUrl) {
    setPreviousPreview({ isOpen, fileUrl });
    setIsLoading(true);
    setError(null);
  }

  // Determine file type from extension if not provided
  const getFileType = (): 'pdf' | 'image' | 'unknown' => {
    const type = fileType?.toLowerCase() || fileName.split('.').pop()?.toLowerCase();
    if (type === 'pdf') return 'pdf';
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(type || '')) return 'image';
    return 'unknown';
  };

  const previewType = getFileType();
  const canPreview = previewType !== 'unknown' && fileUrl;

  const handleLoad = () => {
    setIsLoading(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setError('Δεν ήταν δυνατή η φόρτωση του αρχείου');
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="" size="xl">
      <div className="flex flex-col h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            {previewType === 'pdf' ? (
              <FileText className="w-6 h-6 text-red-500" />
            ) : previewType === 'image' ? (
              <ImageIcon className="w-6 h-6 text-blue-500" />
            ) : (
              <FileText className="w-6 h-6 text-gray-500" />
            )}
            <div>
              <h3 className="font-semibold text-gray-900 truncate max-w-md">{fileName}</h3>
              <p className="text-sm text-gray-500 uppercase">{fileType || 'Αρχείο'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {fileUrl && (
              <>
                <a
                  href={fileUrl}
                  download={fileName}
                  className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Λήψη"
                >
                  <Download className="w-5 h-5" />
                </a>
                <a
                  href={fileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Άνοιγμα σε νέα καρτέλα"
                >
                  <ExternalLink className="w-5 h-5" />
                </a>
              </>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden mt-4 bg-gray-100 rounded-lg relative">
          {isLoading && canPreview && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">{error}</p>
              </div>
            </div>
          )}

          {canPreview && !error && (
            <>
              {previewType === 'pdf' && (
                <iframe
                  src={`${fileUrl}#view=FitH`}
                  className="w-full h-full border-0"
                  onLoad={handleLoad}
                  onError={handleError}
                  title={fileName}
                />
              )}

              {previewType === 'image' && (
                <div className="w-full h-full flex items-center justify-center p-4">
                  <img
                    src={fileUrl}
                    alt={fileName}
                    className="max-w-full max-h-full object-contain"
                    onLoad={handleLoad}
                    onError={handleError}
                  />
                </div>
              )}
            </>
          )}

          {!canPreview && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-600 font-medium mb-2">
                  Η προεπισκόπηση δεν είναι διαθέσιμη
                </p>
                <p className="text-sm text-gray-500 mb-4">
                  Αυτός ο τύπος αρχείου δεν υποστηρίζει προεπισκόπηση
                </p>
                {fileUrl && (
                  <a
                    href={fileUrl}
                    download={fileName}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Λήψη αρχείου
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

export default FilePreviewModal;
