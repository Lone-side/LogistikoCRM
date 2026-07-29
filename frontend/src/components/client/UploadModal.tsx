import { useState, useRef, useCallback } from 'react';
import {
  FileText,
  Upload,
  RefreshCw,
  X,
} from 'lucide-react';
import { Button } from '../../components';
import {
  DOCUMENT_CATEGORY_GROUPS,
  DOCUMENT_CATEGORY_FOLDER_TYPE,
  GREEK_MONTH_NAMES,
} from '../../types';

// Props interface
export interface UploadModalProps {
  onClose: () => void;
  onUpload: (file: File, category?: string, description?: string, year?: number, month?: number) => void;
  isLoading: boolean;
  /** Μήνυμα σφάλματος από το backend (π.χ. μη επιτρεπόμενη κατάληξη) */
  errorMessage?: string | null;
}

export default function UploadModal({
  onClose,
  onUpload,
  isLoading,
  errorMessage,
}: UploadModalProps) {
  const now = new Date();
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState('general');
  const [description, setDescription] = useState('');
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Τι χρειάζεται η κατηγορία: μόνιμα → τίποτα, ετήσια → έτος, μηνιαία → έτος+μήνας
  const folderType = DOCUMENT_CATEGORY_FOLDER_TYPE[category] || 'monthly';
  const needsYear = folderType !== 'permanent';
  const needsMonth = folderType === 'monthly';

  const yearOptions = Array.from({ length: 7 }, (_, i) => now.getFullYear() + 1 - i);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleSubmit = () => {
    if (file) {
      onUpload(
        file,
        category,
        description,
        needsYear ? year : undefined,
        needsMonth ? month : undefined,
      );
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">Μεταφόρτωση Εγγράφου</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {/* Drop zone */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
              accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.zip,.txt,.csv,.xml"
            />
            {file ? (
              <div className="flex items-center justify-center gap-2">
                <FileText className="w-8 h-8 text-blue-600" />
                <span className="font-medium">{file.name}</span>
                <button
                  onClick={() => setFile(null)}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600 mb-1">Σύρετε αρχείο εδώ ή</p>
                <button
                  onClick={() => inputRef.current?.click()}
                  className="text-blue-600 hover:underline"
                >
                  επιλέξτε αρχείο
                </button>
                <p className="text-xs text-gray-400 mt-2">
                  Επιτρεπόμενοι τύποι και μέγεθος βάσει Ρυθμίσεων Αρχειοθέτησης
                </p>
              </>
            )}
          </div>

          {/* Backend error */}
          {errorMessage && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {errorMessage}
            </div>
          )}

          {/* Category (ομαδοποιημένη: Μόνιμα / Μηνιαία / Ετήσια) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Κατηγορία
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg"
            >
              {DOCUMENT_CATEGORY_GROUPS.map((group) => (
                <optgroup key={group.label} label={group.label}>
                  {group.categories.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              {folderType === 'permanent' && 'Θα αποθηκευτεί στον φάκελο 00_ΜΟΝΙΜΑ'}
              {folderType === 'yearend' && 'Θα αποθηκευτεί στον φάκελο 13_ΕΤΗΣΙΑ του έτους'}
              {folderType === 'monthly' && 'Θα αποθηκευτεί στον μηνιαίο φάκελο του πελάτη'}
            </p>
          </div>

          {/* Year / Month (ανάλογα με την κατηγορία) */}
          {needsYear && (
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Έτος
                </label>
                <select
                  value={year}
                  onChange={(e) => setYear(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                >
                  {yearOptions.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
              {needsMonth && (
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Μήνας
                  </label>
                  <select
                    value={month}
                    onChange={(e) => setMonth(parseInt(e.target.value, 10))}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg"
                  >
                    {GREEK_MONTH_NAMES.map((name, i) => (
                      <option key={i + 1} value={i + 1}>{name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Περιγραφή (προαιρετικά)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              placeholder="Π.χ. Τιμολόγιο Δεκεμβρίου 2025"
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 p-4 border-t bg-gray-50">
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button onClick={handleSubmit} disabled={!file || isLoading}>
            {isLoading ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Upload className="w-4 h-4 mr-2" />
            )}
            Μεταφόρτωση
          </Button>
        </div>
      </div>
    </div>
  );
}
