/**
 * FileManager.tsx
 * Full-featured file manager page with browse, search, upload, share functionality
 */

import { useState, useCallback, useMemo } from 'react';
import {
  FolderOpen, Upload, Search, Grid, List, Filter, Star, Share2, Trash2,
  Download, Eye, ChevronRight, Clock, HardDrive,
  MoreVertical, CheckSquare, Square, X, Link2,
  FileText, Image, FileSpreadsheet, File, RefreshCw
} from 'lucide-react';
import { Button } from '../components/Button';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { PageHeader, StatCard } from '../components/ui';
import {
  useFileManagerDocuments,
  useFileManagerStats,
  useBrowseFolders,
  useTags,
  useFavorites,
  useCollections,
  useUploadDocuments,
  useDeleteDocument,
  useBulkDeleteDocuments,
  useAddFavorite,
  useRemoveFavorite,
  useCreateSharedLink,
  downloadDocument,
  getFileColor,
} from '../hooks/useFileManager';
import type {
  FileManagerDocument,
  DocumentFilters,
  ViewMode,
  DocumentCategory,
} from '../types/fileManager';
import { DOCUMENT_CATEGORIES, GREEK_MONTHS } from '../types/fileManager';
import { useClients } from '../hooks/useClients';
import { useObligations } from '../hooks/useObligations';

// File type icon component
function FileIcon({ fileType, size = 24 }: { fileType: string; size?: number }) {
  const type = fileType?.toLowerCase() || '';
  const color = getFileColor(type);

  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type)) {
    return <Image size={size} style={{ color }} />;
  }
  if (['xls', 'xlsx'].includes(type)) {
    return <FileSpreadsheet size={size} style={{ color }} />;
  }
  if (['pdf', 'doc', 'docx'].includes(type)) {
    return <FileText size={size} style={{ color }} />;
  }
  return <File size={size} style={{ color }} />;
}

// Document card for grid view
function DocumentCard({
  document,
  isSelected,
  onSelect,
  onPreview,
  onDownload,
  onShare,
  onFavorite,
  onDelete,
}: {
  document: FileManagerDocument;
  isSelected: boolean;
  onSelect: () => void;
  onPreview: () => void;
  onDownload: () => void;
  onShare: () => void;
  onFavorite: () => void;
  onDelete: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      className={`bg-white rounded-lg border ${isSelected ? 'border-brand-500 ring-2 ring-brand-200' : 'border-slate-200'}
        p-4 hover:shadow-md transition-all cursor-pointer group relative`}
    >
      {/* Selection checkbox */}
      <button
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        className="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        {isSelected ? (
          <CheckSquare size={20} className="text-brand-500" />
        ) : (
          <Square size={20} className="text-slate-400" />
        )}
      </button>

      {/* Menu button */}
      <div className="absolute top-2 right-2">
        <button
          onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu); }}
          className="p-1 rounded hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <MoreVertical size={16} className="text-slate-500" />
        </button>

        {showMenu && (
          <div className="absolute right-0 top-8 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-10 min-w-[150px]">
            {document.can_preview && (
              <button
                onClick={() => { onPreview(); setShowMenu(false); }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2"
              >
                <Eye size={14} /> Προβολή
              </button>
            )}
            <button
              onClick={() => { onDownload(); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2"
            >
              <Download size={14} /> Λήψη
            </button>
            <button
              onClick={() => { onShare(); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2"
            >
              <Share2 size={14} /> Κοινοποίηση
            </button>
            <button
              onClick={() => { onFavorite(); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2"
            >
              <Star size={14} fill={document.is_favorite ? '#F59E0B' : 'none'} />
              {document.is_favorite ? 'Αφαίρεση' : 'Αγαπημένο'}
            </button>
            <hr className="my-1" />
            <button
              onClick={() => { onDelete(); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-sm hover:bg-danger-50 text-danger-600 flex items-center gap-2"
            >
              <Trash2 size={14} /> Διαγραφή
            </button>
          </div>
        )}
      </div>

      {/* File icon */}
      <div className="flex justify-center mb-3 pt-4" role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onPreview(); }} onClick={onPreview}>
        <FileIcon fileType={document.file_type} size={48} />
      </div>

      {/* File info */}
      <div className="text-center" role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onPreview(); }} onClick={onPreview}>
        <p className="font-medium text-slate-900 truncate" title={document.filename}>
          {document.filename}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          {document.file_size_display} • {document.file_type.toUpperCase()}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          {document.client_name}
        </p>
      </div>

      {/* Tags */}
      {document.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2 justify-center">
          {document.tags.slice(0, 2).map((tag) => (
            <span
              key={tag.id}
              className="px-2 py-0.5 text-xs rounded-full"
              style={{ backgroundColor: `${tag.color}20`, color: tag.color }}
            >
              {tag.name}
            </span>
          ))}
          {document.tags.length > 2 && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-500">
              +{document.tags.length - 2}
            </span>
          )}
        </div>
      )}

      {/* Status icons */}
      <div className="flex justify-center gap-2 mt-2">
        {document.is_favorite && <Star size={14} className="text-warning-600" fill="#F59E0B" />}
        {document.shared_links_count > 0 && <Link2 size={14} className="text-brand-500" />}
        {document.version > 1 && (
          <span className="text-xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">v{document.version}</span>
        )}
      </div>
    </div>
  );
}

// Document row for list view
function DocumentRow({
  document,
  isSelected,
  onSelect,
  onPreview,
  onDownload,
  onShare,
  onFavorite,
  onDelete,
}: {
  document: FileManagerDocument;
  isSelected: boolean;
  onSelect: () => void;
  onPreview: () => void;
  onDownload: () => void;
  onShare: () => void;
  onFavorite: () => void;
  onDelete: () => void;
}) {
  return (
    <tr className={`hover:bg-slate-50 ${isSelected ? 'bg-brand-50' : ''}`}>
      <td className="px-4 py-3">
        <button onClick={onSelect}>
          {isSelected ? (
            <CheckSquare size={18} className="text-brand-500" />
          ) : (
            <Square size={18} className="text-slate-400" />
          )}
        </button>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3 cursor-pointer" role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onPreview(); }} onClick={onPreview}>
          <FileIcon fileType={document.file_type} size={24} />
          <div>
            <p className="font-medium text-slate-900">{document.filename}</p>
            <p className="text-xs text-slate-500">{document.client_name}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="px-2 py-1 text-xs rounded-full bg-slate-100 text-slate-600">
          {document.category_display}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-slate-500">{document.file_size_display}</td>
      <td className="px-4 py-3 text-sm text-slate-500">
        {new Date(document.uploaded_at).toLocaleDateString('el-GR')}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {document.tags.slice(0, 2).map((tag) => (
            <span
              key={tag.id}
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: tag.color }}
              title={tag.name}
            />
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <button onClick={onFavorite} className="p-1 rounded hover:bg-slate-100" title="Αγαπημένο">
            <Star size={16} className={document.is_favorite ? 'text-warning-600' : 'text-slate-400'} fill={document.is_favorite ? '#F59E0B' : 'none'} />
          </button>
          {document.can_preview && (
            <button onClick={onPreview} className="p-1 rounded hover:bg-slate-100" title="Προβολή">
              <Eye size={16} className="text-slate-400" />
            </button>
          )}
          <button onClick={onDownload} className="p-1 rounded hover:bg-slate-100" title="Λήψη">
            <Download size={16} className="text-slate-400" />
          </button>
          <button onClick={onShare} className="p-1 rounded hover:bg-slate-100" title="Κοινοποίηση">
            <Share2 size={16} className="text-slate-400" />
          </button>
          <button onClick={onDelete} className="p-1 rounded hover:bg-danger-100" title="Διαγραφή">
            <Trash2 size={16} className="text-slate-400 hover:text-danger-600" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// Upload Modal
function UploadModal({
  isOpen,
  onClose,
  onUpload,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (files: File[], clientId: number, category: DocumentCategory, obligationId?: number) => void;
  isLoading: boolean;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [clientId, setClientId] = useState<number | null>(null);
  const [category, setCategory] = useState<DocumentCategory>('general');
  const [obligationId, setObligationId] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const { data: clientsData } = useClients({ page_size: 1000 });
  const clients = clientsData?.results || [];

  // Fetch pending obligations for selected client
  const { data: obligationsData } = useObligations(
    clientId ? { client: clientId, status: 'pending', page_size: 100 } : undefined
  );
  const obligations = obligationsData?.results || [];

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...droppedFiles]);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSubmit = () => {
    if (files.length > 0 && clientId) {
      onUpload(files, clientId, category, obligationId || undefined);
    }
  };

  const reset = () => {
    setFiles([]);
    setClientId(null);
    setCategory('general');
    setObligationId(null);
  };

  // Reset obligation when client changes
  const handleClientChange = (newClientId: number | null) => {
    setClientId(newClientId);
    setObligationId(null);
  };

  return (
    <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); }} title="Μεταφόρτωση Αρχείων" size="lg">
      <div className="space-y-4">
        {/* Client selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Πελάτης *</label>
          <select
            value={clientId || ''}
            onChange={(e) => handleClientChange(e.target.value ? Number(e.target.value) : null)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
          >
            <option value="">Επιλέξτε πελάτη...</option>
            {clients.map((client) => (
              <option key={client.id} value={client.id}>
                {client.eponimia} ({client.afm})
              </option>
            ))}
          </select>
        </div>

        {/* Category selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Κατηγορία</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as DocumentCategory)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
          >
            {DOCUMENT_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>{cat.label}</option>
            ))}
          </select>
        </div>

        {/* Obligation selection (optional) */}
        {clientId && obligations.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Σύνδεση με Υποχρέωση <span className="text-slate-400 font-normal">(προαιρετικό)</span>
            </label>
            <select
              value={obligationId || ''}
              onChange={(e) => setObligationId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            >
              <option value="">Χωρίς σύνδεση</option>
              {obligations.map((obl) => (
                <option key={obl.id} value={obl.id}>
                  {obl.type_name || obl.type_code} - {String(obl.month).padStart(2, '0')}/{obl.year}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Συνδέστε το αρχείο με μια εκκρεμή υποχρέωση του πελάτη
            </p>
          </div>
        )}

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-slate-400'}`}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.webp,.zip"
          />
          <Upload className="w-10 h-10 mx-auto text-slate-400 mb-3" />
          <p className="text-slate-600 font-medium">Σύρετε αρχεία εδώ ή κάντε κλικ</p>
          <p className="text-sm text-slate-400 mt-1">PDF, DOC, XLS, JPG, PNG, ZIP (max 10MB)</p>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-slate-50 rounded">
                <div className="flex items-center gap-2">
                  <FileIcon fileType={file.name.split('.').pop() || ''} size={20} />
                  <span className="text-sm truncate max-w-[200px]">{file.name}</span>
                  <span className="text-xs text-slate-400">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
                <button onClick={() => removeFile(index)} className="p-1 hover:bg-slate-200 rounded">
                  <X size={16} className="text-slate-500" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="secondary" onClick={() => { reset(); onClose(); }}>Ακύρωση</Button>
          <Button
            onClick={handleSubmit}
            disabled={files.length === 0 || !clientId || isLoading}
          >
            {isLoading ? 'Μεταφόρτωση...' : `Μεταφόρτωση ${files.length} αρχείων`}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// Share Modal
function ShareModal({
  isOpen,
  onClose,
  document,
  onShare,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  document: FileManagerDocument | null;
  onShare: (data: { documentId: number; expiresInDays?: number; password?: string }) => void;
  isLoading: boolean;
}) {
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>(7);
  const [password, setPassword] = useState('');
  const [usePassword, setUsePassword] = useState(false);

  if (!document) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Κοινοποίηση Αρχείου" size="md">
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
          <FileIcon fileType={document.file_type} size={32} />
          <div>
            <p className="font-medium">{document.filename}</p>
            <p className="text-sm text-slate-500">{document.file_size_display}</p>
          </div>
        </div>

        {/* Expiration */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Λήξη συνδέσμου</label>
          <select
            value={expiresInDays || ''}
            onChange={(e) => setExpiresInDays(e.target.value ? Number(e.target.value) : undefined)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md"
          >
            <option value="">Χωρίς λήξη</option>
            <option value="1">1 ημέρα</option>
            <option value="7">7 ημέρες</option>
            <option value="30">30 ημέρες</option>
            <option value="90">90 ημέρες</option>
          </select>
        </div>

        {/* Password protection */}
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={usePassword}
              onChange={(e) => setUsePassword(e.target.checked)}
              className="w-4 h-4 rounded"
            />
            <span className="text-sm text-slate-700">Προστασία με κωδικό</span>
          </label>
          {usePassword && (
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Εισάγετε κωδικό..."
              className="mt-2 w-full px-3 py-2 border border-slate-300 rounded-md"
            />
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="secondary" onClick={onClose}>Ακύρωση</Button>
          <Button
            onClick={() => onShare({
              documentId: document.id,
              expiresInDays,
              password: usePassword ? password : undefined,
            })}
            disabled={isLoading}
          >
            <Link2 size={16} className="mr-2" />
            {isLoading ? 'Δημιουργία...' : 'Δημιουργία Συνδέσμου'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// Preview Modal
function PreviewModal({
  isOpen,
  onClose,
  document,
}: {
  isOpen: boolean;
  onClose: () => void;
  document: FileManagerDocument | null;
}) {
  if (!document) return null;

  const isPdf = document.file_type.toLowerCase() === 'pdf';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(document.file_type.toLowerCase());

  const handleOpenInNewTab = () => {
    if (document.file_url) {
      window.open(document.file_url, '_blank');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={document.filename} size="xl">
      <div className="min-h-[60vh]">
        {isPdf && document.file_url && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-slate-500">
            <FileIcon fileType="pdf" size={80} />
            <p className="mt-4 text-lg font-medium">{document.filename}</p>
            <p className="text-sm text-slate-400 mt-1">{document.file_size_display}</p>
            <div className="flex gap-3 mt-6">
              <Button onClick={handleOpenInNewTab}>
                <Eye size={16} className="mr-2" /> Άνοιγμα σε νέα καρτέλα
              </Button>
              <Button variant="secondary" onClick={() => downloadDocument(document.id, document.filename)}>
                <Download size={16} className="mr-2" /> Λήψη
              </Button>
            </div>
          </div>
        )}
        {isImage && document.file_url && (
          <div className="flex justify-center items-center h-[70vh]">
            <img
              src={document.file_url}
              alt={document.filename}
              className="max-w-full max-h-full object-contain"
            />
          </div>
        )}
        {!isPdf && !isImage && (
          <div className="flex flex-col items-center justify-center h-[40vh] text-slate-500">
            <FileIcon fileType={document.file_type} size={64} />
            <p className="mt-4">Δεν είναι δυνατή η προεπισκόπηση αυτού του τύπου αρχείου.</p>
            <Button
              className="mt-4"
              onClick={() => downloadDocument(document.id, document.filename)}
            >
              <Download size={16} className="mr-2" /> Λήψη αρχείου
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
}

// Folder Browser Sidebar Component
function FolderBrowserSidebar({
  isOpen,
  onClose,
  onNavigate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (filters: { client_id?: number; year?: number; month?: number }) => void;
}) {
  const [selectedClient, setSelectedClient] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);

  // Build browse params based on selection
  const browseParams = useMemo(() => {
    if (!selectedClient) return {};
    if (!selectedYear) return { client_id: selectedClient };
    if (!selectedMonth) return { client_id: selectedClient, year: selectedYear };
    return { client_id: selectedClient, year: selectedYear, month: selectedMonth };
  }, [selectedClient, selectedYear, selectedMonth]);

  const { data: browseData, isLoading: isBrowsing } = useBrowseFolders(browseParams);

  const handleBack = useCallback(() => {
    if (selectedMonth) {
      setSelectedMonth(null);
    } else if (selectedYear) {
      setSelectedYear(null);
    } else if (selectedClient) {
      setSelectedClient(null);
    }
  }, [selectedClient, selectedYear, selectedMonth]);

  const handleSelectClient = (clientId: number) => {
    setSelectedClient(clientId);
    setSelectedYear(null);
    setSelectedMonth(null);
  };

  const handleSelectYear = (year: string) => {
    setSelectedYear(year);
    setSelectedMonth(null);
  };

  const handleSelectMonth = (month: string) => {
    setSelectedMonth(month);
  };

  const handleApplyFilter = () => {
    onNavigate({
      client_id: selectedClient || undefined,
      year: selectedYear ? parseInt(selectedYear) : undefined,
      month: selectedMonth ? parseInt(selectedMonth) : undefined,
    });
    onClose();
  };

  if (!isOpen) return null;

  // Breadcrumb path
  const breadcrumbs: { label: string; onClick: () => void }[] = [
    { label: 'Πελάτες', onClick: () => { setSelectedClient(null); setSelectedYear(null); setSelectedMonth(null); } },
  ];
  if (browseData?.type === 'years' || browseData?.type === 'months' || browseData?.type === 'documents') {
    breadcrumbs.push({
      label: browseData.client.eponimia,
      onClick: () => { setSelectedYear(null); setSelectedMonth(null); },
    });
  }
  if ((browseData?.type === 'months' || browseData?.type === 'documents') && selectedYear) {
    breadcrumbs.push({
      label: selectedYear,
      onClick: () => setSelectedMonth(null),
    });
  }
  if (browseData?.type === 'documents' && selectedMonth) {
    breadcrumbs.push({
      label: GREEK_MONTHS[parseInt(selectedMonth) - 1] || selectedMonth,
      onClick: () => {},
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/30" onClick={onClose} />

      {/* Sidebar */}
      <div className="relative w-96 bg-white h-full shadow-xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <FolderOpen className="text-brand-500" size={20} />
            <h2 className="font-semibold text-slate-900">Περιήγηση Φακέλων</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-200 rounded">
            <X size={20} className="text-slate-500" />
          </button>
        </div>

        {/* Breadcrumbs */}
        <div className="px-4 py-2 border-b bg-slate-50 flex items-center gap-1 text-sm overflow-x-auto">
          {breadcrumbs.map((crumb, index) => (
            <div key={index} className="flex items-center gap-1 shrink-0">
              {index > 0 && <ChevronRight size={14} className="text-slate-400" />}
              <button
                onClick={crumb.onClick}
                className={`hover:text-brand-600 ${index === breadcrumbs.length - 1 ? 'text-brand-600 font-medium' : 'text-slate-600'}`}
              >
                {crumb.label}
              </button>
            </div>
          ))}
        </div>

        {/* Back button */}
        {selectedClient && (
          <div className="px-4 py-2 border-b">
            <button
              onClick={handleBack}
              className="flex items-center gap-2 text-sm text-slate-600 hover:text-brand-600"
            >
              <ChevronRight size={16} className="rotate-180" />
              Πίσω
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isBrowsing ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
            </div>
          ) : browseData?.type === 'clients' ? (
            <div className="space-y-1">
              <p className="text-sm text-slate-500 mb-3">Επιλέξτε πελάτη για περιήγηση:</p>
              {browseData.clients.length === 0 ? (
                <p className="text-slate-400 text-center py-4">Δεν βρέθηκαν πελάτες με αρχεία</p>
              ) : (
                browseData.clients.map((client) => (
                  <button
                    key={client.id}
                    onClick={() => handleSelectClient(client.id)}
                    className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-brand-50 border border-transparent hover:border-brand-200 transition-all"
                  >
                    <div className="flex items-center gap-3">
                      <FolderOpen size={20} className="text-warning-600" />
                      <div className="text-left">
                        <p className="font-medium text-slate-900">{client.eponimia}</p>
                        <p className="text-xs text-slate-500">{client.afm}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-600">
                        {client.document_count} αρχεία
                      </span>
                      <ChevronRight size={16} className="text-slate-400" />
                    </div>
                  </button>
                ))
              )}
            </div>
          ) : browseData?.type === 'years' ? (
            <div className="space-y-1">
              <p className="text-sm text-slate-500 mb-3">Επιλέξτε έτος:</p>
              {browseData.years.length === 0 ? (
                <p className="text-slate-400 text-center py-4">Δεν βρέθηκαν αρχεία</p>
              ) : (
                browseData.years.map((year) => (
                  <button
                    key={year.year}
                    onClick={() => handleSelectYear(String(year.year))}
                    className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-brand-50 border border-transparent hover:border-brand-200 transition-all"
                  >
                    <div className="flex items-center gap-3">
                      <FolderOpen size={20} className="text-brand-500" />
                      <span className="font-medium text-slate-900">{year.year}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-600">
                        {year.count} αρχεία
                      </span>
                      <ChevronRight size={16} className="text-slate-400" />
                    </div>
                  </button>
                ))
              )}
            </div>
          ) : browseData?.type === 'months' ? (
            <div className="space-y-1">
              <p className="text-sm text-slate-500 mb-3">Επιλέξτε μήνα:</p>
              {browseData.months.length === 0 ? (
                <p className="text-slate-400 text-center py-4">Δεν βρέθηκαν αρχεία</p>
              ) : (
                browseData.months.map((m) => (
                  <button
                    key={m.month}
                    onClick={() => handleSelectMonth(String(m.month))}
                    className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-brand-50 border border-transparent hover:border-brand-200 transition-all"
                  >
                    <div className="flex items-center gap-3">
                      <FolderOpen size={20} className="text-success-600" />
                      <span className="font-medium text-slate-900">
                        {String(m.month).padStart(2, '0')} - {GREEK_MONTHS[m.month - 1]}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-600">
                        {m.count} αρχεία
                      </span>
                      <ChevronRight size={16} className="text-slate-400" />
                    </div>
                  </button>
                ))
              )}
            </div>
          ) : browseData?.type === 'documents' ? (
            <div className="space-y-2">
              <p className="text-sm text-slate-500 mb-3">
                Έγγραφα ({browseData.documents.length}):
              </p>
              {browseData.documents.length === 0 ? (
                <p className="text-slate-400 text-center py-4">Δεν βρέθηκαν έγγραφα</p>
              ) : (
                browseData.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 border border-slate-100"
                  >
                    <FileIcon fileType={doc.file_type} size={20} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-500">{doc.file_size_display}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            <p className="text-slate-400 text-center py-4">Φόρτωση...</p>
          )}
        </div>

        {/* Apply filter button */}
        {selectedClient && (
          <div className="p-4 border-t bg-slate-50">
            <Button onClick={handleApplyFilter} className="w-full">
              <Filter size={16} className="mr-2" />
              Εμφάνιση αρχείων
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// Main FileManager component
export default function FileManager() {
  // View state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Folder browser state
  const [folderBrowserOpen, setFolderBrowserOpen] = useState(false);

  // Filter state
  const [filters, setFilters] = useState<DocumentFilters>({
    page: 1,
    page_size: 24,
    ordering: '-uploaded_at',
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Modal state
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [activeDocument, setActiveDocument] = useState<FileManagerDocument | null>(null);

  // Data hooks
  const { data: documentsData, isLoading, refetch } = useFileManagerDocuments(filters);
  const { data: stats } = useFileManagerStats();
  const { data: tags } = useTags();
  useFavorites();
  useCollections();

  // Mutation hooks
  const uploadMutation = useUploadDocuments();
  const deleteMutation = useDeleteDocument();
  const bulkDeleteMutation = useBulkDeleteDocuments();
  const addFavoriteMutation = useAddFavorite();
  const removeFavoriteMutation = useRemoveFavorite();
  const createShareLinkMutation = useCreateSharedLink();

  const documents = useMemo(() => documentsData?.results || [], [documentsData]);
  const totalCount = documentsData?.count || 0;

  // Handlers
  const handleSearch = useCallback(() => {
    setFilters((prev) => ({ ...prev, search: searchQuery, page: 1 }));
  }, [searchQuery]);

  const handleCategoryFilter = useCallback((category: DocumentCategory | '') => {
    setFilters((prev) => ({
      ...prev,
      category: category || undefined,
      page: 1,
    }));
  }, []);

  const handleUpload = useCallback(async (files: File[], clientId: number, category: DocumentCategory, obligationId?: number) => {
    try {
      await uploadMutation.mutateAsync({
        files,
        client_id: clientId,
        document_category: category,
        obligation_id: obligationId,
      });
      setUploadModalOpen(false);
    } catch (error) {
      console.error('Upload error:', error);
    }
  }, [uploadMutation]);

  const handleShare = useCallback(async (data: { documentId: number; expiresInDays?: number; password?: string }) => {
    try {
      const result = await createShareLinkMutation.mutateAsync({
        document_id: data.documentId,
        expires_in_days: data.expiresInDays,
        password: data.password,
      });
      // Copy to clipboard
      const fullUrl = window.location.origin + result.public_url;
      await navigator.clipboard.writeText(fullUrl);
      alert(`Ο σύνδεσμος αντιγράφηκε: ${fullUrl}`);
      setShareModalOpen(false);
    } catch (error) {
      console.error('Share error:', error);
    }
  }, [createShareLinkMutation]);

  const handleDelete = useCallback(async () => {
    if (!activeDocument) return;
    try {
      await deleteMutation.mutateAsync(activeDocument.id);
      setDeleteConfirmOpen(false);
      setActiveDocument(null);
    } catch (error) {
      console.error('Delete error:', error);
    }
  }, [activeDocument, deleteMutation]);

  const handleBulkDelete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    try {
      await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Bulk delete error:', error);
    }
  }, [selectedIds, bulkDeleteMutation]);

  const handleToggleFavorite = useCallback(async (doc: FileManagerDocument) => {
    try {
      if (doc.is_favorite) {
        await removeFavoriteMutation.mutateAsync(doc.id);
      } else {
        await addFavoriteMutation.mutateAsync({ documentId: doc.id });
      }
    } catch (error) {
      console.error('Favorite error:', error);
    }
  }, [addFavoriteMutation, removeFavoriteMutation]);

  const toggleSelection = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)));
    }
  }, [documents, selectedIds.size]);

  // Handler for folder browser navigation
  const handleFolderNavigate = useCallback((newFilters: { client_id?: number; year?: number; month?: number }) => {
    setFilters((prev) => ({
      ...prev,
      client_id: newFilters.client_id,
      year: newFilters.year,
      month: newFilters.month,
      page: 1,
    }));
  }, []);

  // Clear folder filter
  const clearFolderFilter = useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      client_id: undefined,
      year: undefined,
      month: undefined,
      page: 1,
    }));
  }, []);

  // Check if folder filter is active
  const hasFolderFilter = filters.client_id || filters.year || filters.month;

  return (
    <>
      <div className="p-6">
        {/* Header */}
        <PageHeader
          title={
            <span className="flex items-center gap-2">
              <FolderOpen className="text-brand-500" />
              Διαχείριση Αρχείων
            </span>
          }
          subtitle="Οργανώστε, αναζητήστε και κοινοποιήστε τα αρχεία σας"
          actions={
            <>
              <Button variant="secondary" onClick={() => setFolderBrowserOpen(true)}>
                <FolderOpen size={16} className="mr-2" /> Περιήγηση
              </Button>
              <Button variant="secondary" onClick={() => refetch()}>
                <RefreshCw size={16} className="mr-2" /> Ανανέωση
              </Button>
              <Button onClick={() => setUploadModalOpen(true)}>
                <Upload size={16} className="mr-2" /> Μεταφόρτωση
              </Button>
            </>
          }
        />

        {/* Active folder filter banner */}
        {hasFolderFilter && (
          <div className="bg-brand-50 border border-brand-200 rounded-lg p-3 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-brand-700">
              <FolderOpen size={18} />
              <span>
                Φίλτρο φακέλου:
                {filters.client_id && ' Πελάτης'}
                {filters.year && ` / ${filters.year}`}
                {filters.month && ` / ${GREEK_MONTHS[(filters.month || 1) - 1]}`}
              </span>
            </div>
            <button
              onClick={clearFolderFilter}
              className="flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
            >
              <X size={16} /> Καθαρισμός
            </button>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard
              icon={File}
              label="Συνολικά Αρχεία"
              value={stats.total_documents}
              color="#3B82F6"
            />
            <StatCard
              icon={HardDrive}
              label="Αποθηκευτικός Χώρος"
              value={stats.total_size_display}
              color="#10B981"
            />
            <StatCard
              icon={Clock}
              label="Πρόσφατα (7 ημέρες)"
              value={stats.recent_uploads_count}
              color="#F59E0B"
            />
            <StatCard
              icon={Link2}
              label="Ενεργοί Σύνδεσμοι"
              value={stats.active_shared_links}
              color="#8B5CF6"
            />
          </div>
        )}

        {/* Search and filters bar */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-6">
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px] relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Αναζήτηση αρχείων..."
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              />
            </div>

            {/* Category filter */}
            <select
              value={filters.category || ''}
              onChange={(e) => handleCategoryFilter(e.target.value as DocumentCategory | '')}
              className="px-3 py-2 border border-slate-300 rounded-lg"
            >
              <option value="">Όλες οι κατηγορίες</option>
              {DOCUMENT_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>{cat.label}</option>
              ))}
            </select>

            {/* View mode toggle */}
            <div className="flex items-center border border-slate-300 rounded-lg overflow-hidden">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 ${viewMode === 'grid' ? 'bg-brand-50 text-brand-600' : 'text-slate-500'}`}
              >
                <Grid size={18} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 ${viewMode === 'list' ? 'bg-brand-50 text-brand-600' : 'text-slate-500'}`}
              >
                <List size={18} />
              </button>
            </div>

            {/* More filters */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-3 py-2 border rounded-lg ${showFilters ? 'border-brand-500 text-brand-600' : 'border-slate-300 text-slate-500'}`}
            >
              <Filter size={18} /> Φίλτρα
            </button>
          </div>

          {/* Extended filters */}
          {showFilters && (
            <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm text-slate-500 mb-1">Έτος</label>
                <select
                  value={filters.year || ''}
                  onChange={(e) => setFilters((prev) => ({ ...prev, year: e.target.value ? Number(e.target.value) : undefined }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  <option value="">Όλα</option>
                  {[2025, 2024, 2023, 2022].map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-500 mb-1">Μήνας</label>
                <select
                  value={filters.month || ''}
                  onChange={(e) => setFilters((prev) => ({ ...prev, month: e.target.value ? Number(e.target.value) : undefined }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  <option value="">Όλοι</option>
                  {GREEK_MONTHS.map((month, index) => (
                    <option key={index} value={index + 1}>{month}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-500 mb-1">Τύπος αρχείου</label>
                <select
                  value={filters.file_type || ''}
                  onChange={(e) => setFilters((prev) => ({ ...prev, file_type: e.target.value || undefined }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  <option value="">Όλοι</option>
                  <option value="pdf">PDF</option>
                  <option value="xlsx">Excel</option>
                  <option value="docx">Word</option>
                  <option value="jpg">Εικόνες</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-500 mb-1">Ετικέτα</label>
                <select
                  value={filters.tag || ''}
                  onChange={(e) => setFilters((prev) => ({ ...prev, tag: e.target.value || undefined }))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg"
                >
                  <option value="">Όλες</option>
                  {tags?.map((tag) => (
                    <option key={tag.id} value={tag.name}>{tag.name}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Bulk actions bar */}
        {selectedIds.size > 0 && (
          <div className="bg-brand-50 border border-brand-200 rounded-lg p-3 mb-4 flex items-center justify-between">
            <span className="text-brand-700">
              Επιλεγμένα: {selectedIds.size} αρχεία
            </span>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => setSelectedIds(new Set())}>
                Ακύρωση
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleBulkDelete}
                className="text-danger-600 hover:bg-danger-50"
              >
                <Trash2 size={14} className="mr-1" /> Διαγραφή
              </Button>
            </div>
          </div>
        )}

        {/* Documents display */}
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500"></div>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <FolderOpen size={48} className="mx-auto mb-4 text-slate-300" />
            <p>Δεν βρέθηκαν αρχεία</p>
            <Button className="mt-4" onClick={() => setUploadModalOpen(true)}>
              <Upload size={16} className="mr-2" /> Μεταφορτώστε το πρώτο αρχείο
            </Button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {documents.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                isSelected={selectedIds.has(doc.id)}
                onSelect={() => toggleSelection(doc.id)}
                onPreview={() => { setActiveDocument(doc); setPreviewModalOpen(true); }}
                onDownload={() => downloadDocument(doc.id, doc.filename)}
                onShare={() => { setActiveDocument(doc); setShareModalOpen(true); }}
                onFavorite={() => handleToggleFavorite(doc)}
                onDelete={() => { setActiveDocument(doc); setDeleteConfirmOpen(true); }}
              />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <button onClick={selectAll}>
                      {selectedIds.size === documents.length ? (
                        <CheckSquare size={18} className="text-brand-500" />
                      ) : (
                        <Square size={18} className="text-slate-400" />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Αρχείο</th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Κατηγορία</th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Μέγεθος</th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Ημερομηνία</th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Ετικέτες</th>
                  <th className="px-4 py-3 text-left text-xs uppercase tracking-wide font-medium text-slate-500">Ενέργειες</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    document={doc}
                    isSelected={selectedIds.has(doc.id)}
                    onSelect={() => toggleSelection(doc.id)}
                    onPreview={() => { setActiveDocument(doc); setPreviewModalOpen(true); }}
                    onDownload={() => downloadDocument(doc.id, doc.filename)}
                    onShare={() => { setActiveDocument(doc); setShareModalOpen(true); }}
                    onFavorite={() => handleToggleFavorite(doc)}
                    onDelete={() => { setActiveDocument(doc); setDeleteConfirmOpen(true); }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalCount > (filters.page_size || 24) && (
          <div className="flex justify-center items-center gap-4 mt-6">
            <Button
              variant="secondary"
              disabled={filters.page === 1}
              onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page || 1) - 1 }))}
            >
              Προηγούμενη
            </Button>
            <span className="text-slate-500">
              Σελίδα {filters.page} από {Math.ceil(totalCount / (filters.page_size || 24))}
            </span>
            <Button
              variant="secondary"
              disabled={(filters.page || 1) * (filters.page_size || 24) >= totalCount}
              onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page || 1) + 1 }))}
            >
              Επόμενη
            </Button>
          </div>
        )}
      </div>

      {/* Modals */}
      <FolderBrowserSidebar
        isOpen={folderBrowserOpen}
        onClose={() => setFolderBrowserOpen(false)}
        onNavigate={handleFolderNavigate}
      />

      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUpload={handleUpload}
        isLoading={uploadMutation.isPending}
      />

      <ShareModal
        isOpen={shareModalOpen}
        onClose={() => { setShareModalOpen(false); setActiveDocument(null); }}
        document={activeDocument}
        onShare={handleShare}
        isLoading={createShareLinkMutation.isPending}
      />

      <PreviewModal
        isOpen={previewModalOpen}
        onClose={() => { setPreviewModalOpen(false); setActiveDocument(null); }}
        document={activeDocument}
      />

      <ConfirmDialog
        isOpen={deleteConfirmOpen}
        onClose={() => { setDeleteConfirmOpen(false); setActiveDocument(null); }}
        onConfirm={handleDelete}
        title="Διαγραφή Αρχείου"
        message={`Είστε σίγουροι ότι θέλετε να διαγράψετε το αρχείο "${activeDocument?.filename}";`}
        confirmText="Διαγραφή"
        cancelText="Ακύρωση"
        variant="danger"
      />
    </>
  );
}
