import { useMemo, useState } from 'react';
import {
  FileText,
  Upload,
  RefreshCw,
  Eye,
  Download,
  Trash2,
  Image as ImageIcon,
  File,
  Search,
  ChevronDown,
  ChevronRight,
  Folder,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '../../components';
import { FilePreviewModal } from '../FilePreviewModal';
import type { ClientDocument } from '../../types';
import {
  DOCUMENT_CATEGORIES,
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_CATEGORY_FOLDER_TYPE,
  GREEK_MONTH_NAMES,
} from '../../types';
import type { ClientDocumentFilters } from '../../hooks/useClientDetails';

// Props interface
export interface ClientDocumentsTabProps {
  data: { documents: ClientDocument[] } | undefined;
  isLoading: boolean;
  filters: ClientDocumentFilters;
  onFiltersChange: (filters: ClientDocumentFilters) => void;
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
    return <FileText className="w-5 h-5 text-blue-500" />;
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
        ${version > 1 ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}
      `}
    >
      v{version}
    </span>
  );
}

// Ετικέτα ομάδας: "2026 · Μάρτιος" για μηνιαία, "Μόνιμα" για permanent, "2026 · Ετήσια"
function groupKey(doc: ClientDocument): string {
  const folderType = DOCUMENT_CATEGORY_FOLDER_TYPE[doc.document_category] || 'monthly';
  if (folderType === 'permanent') return 'permanent';
  if (folderType === 'yearend') return `${doc.year || '—'}|yearend`;
  return `${doc.year || '—'}|${doc.month || 0}`;
}

function groupLabel(key: string): string {
  if (key === 'permanent') return '📌 Μόνιμα Έγγραφα (00_ΜΟΝΙΜΑ)';
  const [year, part] = key.split('|');
  if (part === 'yearend') return `${year} · Ετήσιες Δηλώσεις (13_ΕΤΗΣΙΑ)`;
  const month = parseInt(part, 10);
  return month >= 1 && month <= 12 ? `${year} · ${GREEK_MONTH_NAMES[month - 1]}` : `${year}`;
}

// Ταξινόμηση ομάδων: μόνιμα πρώτα, μετά νεότερο έτος/μήνας πρώτα
function compareGroups(a: string, b: string): number {
  if (a === 'permanent') return -1;
  if (b === 'permanent') return 1;
  const [ay, ap] = a.split('|');
  const [by, bp] = b.split('|');
  if (ay !== by) return by.localeCompare(ay);
  if (ap === 'yearend') return -1;
  if (bp === 'yearend') return 1;
  return parseInt(bp, 10) - parseInt(ap, 10);
}

export default function ClientDocumentsTab({
  data,
  isLoading,
  filters,
  onFiltersChange,
  onUpload,
  onDelete,
}: ClientDocumentsTabProps) {
  const [previewDoc, setPreviewDoc] = useState<ClientDocument | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [searchInput, setSearchInput] = useState(filters.search || '');

  const canPreview = (doc: ClientDocument) => {
    const type = doc.file_type?.toLowerCase();
    return ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type);
  };

  // Ομαδοποίηση: έτος/μήνας (ή Μόνιμα/Ετήσια) → κατηγορία
  const groups = useMemo(() => {
    const docs = data?.documents || [];
    const byGroup = new Map<string, Map<string, ClientDocument[]>>();
    for (const doc of docs) {
      const key = groupKey(doc);
      if (!byGroup.has(key)) byGroup.set(key, new Map());
      const byCategory = byGroup.get(key)!;
      const cat = doc.document_category || 'general';
      if (!byCategory.has(cat)) byCategory.set(cat, []);
      byCategory.get(cat)!.push(doc);
    }
    return [...byGroup.entries()].sort(([a], [b]) => compareGroups(a, b));
  }, [data]);

  // Διαθέσιμα έτη για το φίλτρο (από τα δεδομένα + τρέχον)
  const availableYears = useMemo(() => {
    const years = new Set<number>([new Date().getFullYear()]);
    (data?.documents || []).forEach((d) => d.year && years.add(d.year));
    return [...years].sort((a, b) => b - a);
  }, [data]);

  const applySearch = () => {
    onFiltersChange({ ...filters, search: searchInput || undefined });
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

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            onBlur={applySearch}
            placeholder="Αναζήτηση αρχείου..."
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg"
          />
        </div>

        {/* Year */}
        <select
          value={filters.year || ''}
          onChange={(e) =>
            onFiltersChange({ ...filters, year: e.target.value ? parseInt(e.target.value, 10) : undefined })
          }
          className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white"
        >
          <option value="">Όλα τα έτη</option>
          {availableYears.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        {/* Category */}
        <select
          value={filters.category || ''}
          onChange={(e) => onFiltersChange({ ...filters, category: e.target.value || undefined })}
          className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white"
        >
          <option value="">Όλες οι κατηγορίες</option>
          {DOCUMENT_CATEGORIES.map((cat) => (
            <option key={cat.value} value={cat.value}>{cat.label}</option>
          ))}
        </select>

        {/* Current versions only */}
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer whitespace-nowrap">
          <input
            type="checkbox"
            checked={filters.current_only || false}
            onChange={(e) => onFiltersChange({ ...filters, current_only: e.target.checked || undefined })}
            className="rounded border-gray-300"
          />
          Μόνο τρέχουσες εκδόσεις
        </label>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
        </div>
      )}

      {/* Grouped documents */}
      {!isLoading && data && (
        <div className="space-y-4">
          {groups.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p>Δεν υπάρχουν έγγραφα</p>
              <p className="text-sm mt-1">Κάντε κλικ στο "Μεταφόρτωση" για να προσθέσετε</p>
            </div>
          ) : (
            groups.map(([key, byCategory]) => {
              const isCollapsed = collapsed[key];
              const count = [...byCategory.values()].reduce((n, docs) => n + docs.length, 0);
              return (
                <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* Group header */}
                  <button
                    onClick={() => setCollapsed((c) => ({ ...c, [key]: !c[key] }))}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-2 font-medium text-gray-800">
                      {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      <Folder className="w-4 h-4 text-amber-500" />
                      {groupLabel(key)}
                    </div>
                    <span className="text-xs text-gray-500">{count} αρχεία</span>
                  </button>

                  {/* Categories inside group */}
                  {!isCollapsed && (
                    <div className="p-3 space-y-3">
                      {[...byCategory.entries()].map(([cat, docs]) => (
                        <div key={cat}>
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                            {DOCUMENT_CATEGORY_LABELS[cat] || cat}
                          </p>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {docs.map((doc) => (
                              <div
                                key={doc.id}
                                className="border border-gray-200 rounded-lg p-3 hover:border-blue-300 hover:shadow-sm transition-all"
                              >
                                <div className="flex items-center gap-3">
                                  <div className="w-9 h-9 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
                                    {getFileIcon(doc.file_type)}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <p className="font-medium text-gray-900 truncate text-sm" title={doc.filename}>
                                      {doc.original_filename || doc.filename}
                                    </p>
                                    <div className="flex items-center gap-2 mt-0.5">
                                      <VersionBadge version={doc.version} />
                                      {doc.is_current === false && (
                                        <span className="text-xs text-gray-400">παλιά έκδοση</span>
                                      )}
                                      {doc.afm_mismatch && (
                                        <span
                                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                                          title="Το ΑΦΜ μέσα στο έγγραφο δεν αντιστοιχεί στον πελάτη — πιθανώς λάθος φάκελος"
                                        >
                                          <AlertTriangle className="w-3 h-3" />
                                          ΑΦΜ;
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* File info + actions */}
                                <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                                  <span className="text-xs text-gray-500">
                                    {doc.file_size_display ? `${doc.file_size_display} · ` : ''}
                                    {new Date(doc.uploaded_at).toLocaleDateString('el-GR')}
                                  </span>
                                  <div className="flex gap-0.5">
                                    {canPreview(doc) && (
                                      <button
                                        onClick={() => setPreviewDoc(doc)}
                                        className="p-1.5 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                                        title="Προεπισκόπηση"
                                      >
                                        <Eye className="w-4 h-4" />
                                      </button>
                                    )}
                                    {doc.file_url && (
                                      <a
                                        href={doc.file_url}
                                        download={doc.filename}
                                        className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                                        title="Λήψη"
                                      >
                                        <Download className="w-4 h-4" />
                                      </a>
                                    )}
                                    <button
                                      onClick={() => onDelete(doc.id)}
                                      className="p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors"
                                      title="Διαγραφή"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
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
