import { useState } from 'react';
import {
  FileText,
  Upload,
  RefreshCw,
  Eye,
  Download,
  Trash2,
  Image as ImageIcon,
  File,
} from 'lucide-react';
import { Button } from '../../components';
import { FilePreviewModal } from '../FilePreviewModal';
import type { ClientDocument } from '../../types';

// Props interface
export interface ClientDocumentsTabProps {
  data: { documents: ClientDocument[] } | undefined;
  isLoading: boolean;
  onUpload: () => void;
  onDelete: (docId: number) => void;
}

// File type icon mapping
function getFileIcon(fileType: string) {
  const type = fileType?.toLowerCase();
  if (type === 'pdf') {
    return <FileText className="w-5 h-5 text-red-500" />;
  }
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type)) {
    return <ImageIcon className="w-5 h-5 text-green-500" />;
  }
  if (['doc', 'docx'].includes(type)) {
    return <FileText className="w-5 h-5 text-brand-500" />;
  }
  if (['xls', 'xlsx'].includes(type)) {
    return <FileText className="w-5 h-5 text-green-600" />;
  }
  return <File className="w-5 h-5 text-gray-500" />;
}

// Version badge component
function VersionBadge({ version }: { version?: number }) {
  if (!version) return null;

  return (
    <span
      className={`
        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
        ${version > 1 ? 'bg-brand-100 text-brand-800' : 'bg-green-100 text-green-800'}
      `}
    >
      v{version}
    </span>
  );
}

export default function ClientDocumentsTab({
  data,
  isLoading,
  onUpload,
  onDelete,
}: ClientDocumentsTabProps) {
  const [previewDoc, setPreviewDoc] = useState<ClientDocument | null>(null);

  const canPreview = (doc: ClientDocument) => {
    const type = doc.file_type?.toLowerCase();
    return ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type);
  };

  return (
    <div className="space-y-4">
      {/* Header with upload button */}
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-medium text-gray-700">
          {data ? `${data.documents.length} έγγραφα` : 'Έγγραφα'}
        </h3>
        <Button onClick={onUpload}>
          <Upload className="w-4 h-4 mr-2" />
          Μεταφόρτωση
        </Button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
        </div>
      )}

      {/* Documents grid */}
      {!isLoading && data && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.documents.length === 0 ? (
            <div className="col-span-full text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p>Δεν υπάρχουν έγγραφα</p>
              <p className="text-sm mt-1">Κάντε κλικ στο "Μεταφόρτωση" για να προσθέσετε</p>
            </div>
          ) : (
            data.documents.map((doc) => (
              <div
                key={doc.id}
                className="border border-gray-200 rounded-lg p-4 hover:border-brand-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                      {getFileIcon(doc.file_type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate" title={doc.filename}>
                        {doc.original_filename || doc.filename}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500">
                          {doc.category_display || doc.document_category}
                        </span>
                        <VersionBadge version={doc.version} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* File info */}
                <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
                  {doc.file_size_display && (
                    <span>{doc.file_size_display}</span>
                  )}
                  {doc.file_size_display && <span>•</span>}
                  <span>{new Date(doc.uploaded_at).toLocaleDateString('el-GR')}</span>
                  {doc.uploaded_by && (
                    <>
                      <span>•</span>
                      <span>{doc.uploaded_by}</span>
                    </>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                  <span className="text-xs text-gray-400 uppercase">
                    {doc.file_type}
                  </span>
                  <div className="flex gap-1">
                    {/* Preview button */}
                    {canPreview(doc) && (
                      <button
                        onClick={() => setPreviewDoc(doc)}
                        className="p-1.5 text-brand-600 hover:bg-brand-50 rounded transition-colors"
                        title="Προεπισκόπηση"
                        aria-label={`Προεπισκόπηση: ${doc.filename}`}
                      >
                        <Eye className="w-4 h-4" aria-hidden="true" />
                      </button>
                    )}

                    {/* Download button */}
                    {doc.file_url && (
                      <a
                        href={doc.file_url}
                        download={doc.filename}
                        className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                        title="Λήψη"
                        aria-label={`Λήψη: ${doc.filename}`}
                      >
                        <Download className="w-4 h-4" aria-hidden="true" />
                      </a>
                    )}

                    {/* Delete button */}
                    <button
                      onClick={() => onDelete(doc.id)}
                      className="p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors"
                      title="Διαγραφή"
                      aria-label={`Διαγραφή: ${doc.filename}`}
                    >
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Preview Modal */}
      <FilePreviewModal
        isOpen={!!previewDoc}
        onClose={() => setPreviewDoc(null)}
        fileUrl={previewDoc?.file_url || null}
        fileName={previewDoc?.filename || ''}
        fileType={previewDoc?.file_type}
      />
    </div>
  );
}
