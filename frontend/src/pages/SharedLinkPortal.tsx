/**
 * SharedLinkPortal.tsx
 * Public page for accessing shared files/folders (no authentication required)
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import {
  File, FileText, FileSpreadsheet, Image, Download, Lock, Mail,
  AlertCircle, Loader2, FolderOpen, Upload, CheckCircle, X, AlertTriangle,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import { Button } from '../components/Button';
import apiClient from '../api/client';
import type { PublicSharedContent, PortalUploadResult } from '../types/fileManager';

// File type icon
function FileIcon({ fileType, size = 24 }: { fileType: string; size?: number }) {
  const type = fileType?.toLowerCase() || '';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(type)) {
    return <Image size={size} className="text-purple-500" />;
  }
  if (['xls', 'xlsx'].includes(type)) {
    return <FileSpreadsheet size={size} className="text-green-500" />;
  }
  if (['pdf', 'doc', 'docx'].includes(type)) {
    return <FileText size={size} className="text-red-500" />;
  }
  return <File size={size} className="text-gray-500" />;
}

// Περιοχή upload για τον πελάτη (εμφανίζεται όταν το link επιτρέπει upload)
export function PortalUploadSection({
  token,
  content,
  email,
  onUploaded,
}: {
  token: string;
  content: PublicSharedContent;
  email: string;
  onUploaded?: () => void;
}) {
  const request = content.document_request || null;
  const pendingItems = request ? request.items.filter((i) => !i.is_received) : [];
  const [files, setFiles] = useState<File[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<number | ''>(
    pendingItems.length > 0 ? pendingItems[0].id : ''
  );
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<PortalUploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const maxFiles = selectedItemId !== '' ? 1 : 10;

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)].slice(0, maxFiles));
    setResult(null);
    setUploadError(null);
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));
      if (content.access_token) formData.append('auth', content.access_token);
      if (email) formData.append('email', email);
      if (selectedItemId !== '') formData.append('request_item_id', String(selectedItemId));
      const response = await apiClient.post<PortalUploadResult>(
        `/share/${token}/upload/`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setResult(response.data);
      setFiles([]);
      if (onUploaded) onUploaded();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: PortalUploadResult & { error?: string } } };
      if (axiosErr.response?.data?.errors?.length) {
        setResult(axiosErr.response.data);
        setFiles([]);
      } else {
        setUploadError(axiosErr.response?.data?.error || 'Σφάλμα κατά τη μεταφόρτωση');
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <Upload className="w-5 h-5 text-blue-500" />
        <h2 className="font-bold text-gray-900">Αποστολή Εγγράφων στο Λογιστήριο</h2>
      </div>

      {request && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
          <p className="font-semibold text-orange-900 mb-2">
            Ζητούμενα έγγραφα — {request.title}
          </p>
          {request.notes && (
            <p className="text-sm text-orange-800 mb-2 whitespace-pre-line">{request.notes}</p>
          )}
          <ul className="space-y-1.5">
            {request.items.map((item) => (
              <li key={item.id} className="flex items-center gap-2 text-sm">
                {item.is_received ? (
                  <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
                ) : (
                  <Circle className="w-4 h-4 text-orange-400 flex-shrink-0" />
                )}
                <span className={item.is_received ? 'text-gray-400 line-through' : 'text-gray-800'}>
                  {item.label}
                </span>
                {item.is_received && (
                  <span className="text-xs text-green-600">Ελήφθη</span>
                )}
              </li>
            ))}
          </ul>
          {request.due_date && (
            <p className="text-xs text-orange-700 mt-2">
              Προθεσμία: {new Date(request.due_date).toLocaleDateString('el-GR')}
            </p>
          )}
        </div>
      )}

      {pendingItems.length > 0 && (
        <div className="mb-4">
          <label
            htmlFor="portal-target-document"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Σε ποιο έγγραφο αντιστοιχεί το αρχείο;
          </label>
          <select
            id="portal-target-document"
            value={selectedItemId}
            onChange={(e) => {
              const value = e.target.value;
              setSelectedItemId(value === '' ? '' : Number(value));
              setFiles([]);
            }}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            {pendingItems.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
            <option value="">Άλλο / χωρίς αντιστοίχιση</option>
          </select>
        </div>
      )}

      {content.upload_note && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-800 whitespace-pre-line">
          {content.upload_note}
        </div>
      )}

      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
        }`}
        onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
          accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.zip,.txt,.csv,.xml"
        />
        <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-600 mb-1">Σύρετε αρχεία εδώ ή</p>
        <button
          onClick={() => inputRef.current?.click()}
          className="text-blue-600 hover:underline font-medium"
        >
          επιλέξτε αρχεία
        </button>
        <p className="text-xs text-gray-400 mt-2">{selectedItemId !== '' ? 'Ένα αρχείο για το επιλεγμένο έγγραφο' : 'Έως 10 αρχεία ανά αποστολή'}</p>
      </div>

      {/* Selected files */}
      {files.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between text-sm bg-gray-50 rounded px-3 py-1.5">
              <span className="truncate">{f.name}</span>
              <button
                onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                className="p-0.5 hover:bg-gray-200 rounded"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          ))}
        </div>
      )}

      {uploadError && (
        <div className="mt-3 bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 rounded-lg text-sm flex items-center gap-2">
          <AlertCircle size={16} />
          {uploadError}
        </div>
      )}

      {/* Upload result */}
      {result && (
        <div className="mt-3 space-y-1.5 text-sm">
          {result.uploaded.map((u, i) => (
            <div key={i} className="flex items-center gap-2 bg-green-50 border border-green-200 rounded px-3 py-2 text-green-800">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span className="truncate">{u.filename}</span>
              {u.warning && (
                <span className="flex items-center gap-1 text-amber-700 text-xs ml-auto shrink-0">
                  <AlertTriangle className="w-3.5 h-3.5" /> {u.warning}
                </span>
              )}
            </div>
          ))}
          {result.errors.map((e, i) => (
            <div key={i} className="flex items-center gap-2 bg-red-50 border border-red-200 rounded px-3 py-2 text-red-700">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span className="truncate">{e.filename}</span>
              <span className="text-xs ml-auto shrink-0">{e.error}</span>
            </div>
          ))}
        </div>
      )}

      {files.length > 0 && (
        <Button onClick={handleUpload} disabled={uploading} className="w-full mt-4 py-3">
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Αποστολή...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 mr-2" />
              Αποστολή {files.length} αρχείων
            </>
          )}
        </Button>
      )}
    </div>
  );
}

export default function SharedLinkPortal() {
  const { token } = useParams<{ token: string }>();

  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requiresAuth, setRequiresAuth] = useState(false);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [needsEmail, setNeedsEmail] = useState(false);
  const [linkName, setLinkName] = useState('');
  const [accessLevel, setAccessLevel] = useState<'view' | 'download'>('download');

  // Auth form state
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authenticating, setAuthenticating] = useState(false);

  // Content state
  const [content, setContent] = useState<PublicSharedContent | null>(null);


  // Initial load
  const fetchSharedContent = useCallback(async () => {
    try {
      const response = await apiClient.get(`/share/${token}/`);
      const data = response.data;

      if (data.requires_auth) {
        setRequiresAuth(true);
        setNeedsPassword(data.needs_password);
        setNeedsEmail(data.needs_email);
        setLinkName(data.name);
        setAccessLevel(data.access_level);
      } else {
        setContent(data);
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { error?: string } } };
      if (axiosErr.response?.status === 410) {
        setError(axiosErr.response?.data?.error || 'Ο σύνδεσμος δεν είναι πλέον διαθέσιμος');
      } else {
        setError('Σφάλμα κατά τη φόρτωση');
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      setError('Μη έγκυρος σύνδεσμος');
      setLoading(false);
      return;
    }
    fetchSharedContent();
  }, [token, fetchSharedContent]);

  // Handle authentication
  const handleAuthenticate = async () => {
    if (needsPassword && !password) {
      setAuthError('Εισάγετε τον κωδικό');
      return;
    }
    if (needsEmail && !email) {
      setAuthError('Εισάγετε το email σας');
      return;
    }

    setAuthenticating(true);
    setAuthError(null);

    try {
      const response = await apiClient.post(`/share/${token}/`, {
        password: needsPassword ? password : undefined,
        email: needsEmail ? email : undefined,
      });
      setContent(response.data);
      setRequiresAuth(false);
    } catch (err: unknown) {
      setAuthError(
        axios.isAxiosError<{ error?: string }>(err)
          ? err.response?.data?.error || 'Σφάλμα επαλήθευσης'
          : 'Σφάλμα επαλήθευσης'
      );
    } finally {
      setAuthenticating(false);
    }
  };

  // Handle download (με το access token για προστατευμένα links)
  const handleDownload = async (docId?: number) => {
    try {
      const params = new URLSearchParams();
      if (docId) params.set('doc_id', String(docId));
      if (content?.access_token) params.set('auth', content.access_token);
      const query = params.toString();
      window.open(`/accounting/share/${token}/download/${query ? `?${query}` : ''}`, '_blank');
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-gray-500">Φόρτωση...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Σφάλμα Πρόσβασης</h1>
          <p className="text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  // Authentication required
  if (requiresAuth) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Lock className="w-8 h-8 text-blue-500" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">{linkName || 'Κοινόχρηστο Αρχείο'}</h1>
            <p className="text-gray-500 text-sm mt-1">
              {accessLevel === 'view' ? 'Μόνο προβολή' : 'Προβολή & Λήψη'}
            </p>
          </div>

          {/* Auth form */}
          <div className="space-y-4">
            {needsPassword && (
              <div>
                <label
                  htmlFor="portal-password"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Κωδικός πρόσβασης
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="portal-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAuthenticate()}
                    placeholder="Εισάγετε τον κωδικό..."
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            )}

            {needsEmail && (
              <div>
                <label
                  htmlFor="portal-email"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
                    id="portal-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAuthenticate()}
                    placeholder="Εισάγετε το email σας..."
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            )}

            {authError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
                <AlertCircle size={16} />
                {authError}
              </div>
            )}

            <Button
              onClick={handleAuthenticate}
              disabled={authenticating}
              className="w-full py-3"
            >
              {authenticating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Επαλήθευση...
                </>
              ) : (
                'Πρόσβαση'
              )}
            </Button>
          </div>

          {/* Footer */}
          <div className="mt-6 pt-6 border-t border-gray-200 text-center">
            <p className="text-xs text-gray-400">
              Ασφαλής σύνδεσμος από LogistikoCRM
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Content display
  if (!content) {
    return null;
  }

  // Single document view
  if (content.type === 'document' && content.document) {
    const doc = content.document;
    const isPdf = doc.file_type.toLowerCase() === 'pdf';
    const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(doc.file_type.toLowerCase());

    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileIcon fileType={doc.file_type} size={32} />
              <div>
                <h1 className="font-bold text-gray-900">{doc.filename}</h1>
                <p className="text-sm text-gray-500">{doc.file_size_display}</p>
              </div>
            </div>
            {doc.can_download && (
              <Button onClick={() => handleDownload()}>
                <Download size={16} className="mr-2" />
                Λήψη
              </Button>
            )}
          </div>
        </header>

        {/* Preview */}
        <div className="max-w-6xl mx-auto p-4">
          {content.allow_upload && token && (
            <PortalUploadSection token={token} content={content} email={email} onUploaded={fetchSharedContent} />
          )}
          {isPdf && doc.preview_url ? (
            <div className="bg-white rounded-lg shadow-lg overflow-hidden">
              <iframe
                src={doc.preview_url}
                className="w-full h-[80vh]"
                title={doc.filename}
              />
            </div>
          ) : isImage && doc.preview_url ? (
            <div className="bg-white rounded-lg shadow-lg p-8 flex justify-center">
              <img
                src={doc.preview_url}
                alt={doc.filename}
                className="max-w-full max-h-[70vh] object-contain"
              />
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-lg p-16 text-center">
              <FileIcon fileType={doc.file_type} size={64} />
              <p className="mt-4 text-gray-500">
                Δεν είναι δυνατή η προεπισκόπηση αυτού του τύπου αρχείου.
              </p>
              {doc.can_download && (
                <Button className="mt-4" onClick={() => handleDownload()}>
                  <Download size={16} className="mr-2" />
                  Λήψη αρχείου
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Folder view
  if (content.type === 'folder' && content.documents) {
    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-4">
          <div className="max-w-6xl mx-auto">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <FolderOpen className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <h1 className="font-bold text-gray-900">{content.name}</h1>
                {content.client && (
                  <p className="text-sm text-gray-500">
                    {content.client.eponimia} • ΑΦΜ: {content.client.afm}
                  </p>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Documents list */}
        <div className="max-w-6xl mx-auto p-4">
          {content.allow_upload && token && (
            <PortalUploadSection token={token} content={content} email={email} onUploaded={fetchSharedContent} />
          )}
          <div className="bg-white rounded-lg shadow-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
              <p className="text-sm text-gray-600">
                {content.documents.length} αρχεία
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {content.documents.map((doc, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <FileIcon fileType={doc.file_type} size={24} />
                    <div>
                      <p className="font-medium text-gray-900">{doc.filename}</p>
                      <p className="text-sm text-gray-500">
                        {doc.category} • {doc.file_size_display} •{' '}
                        {new Date(doc.uploaded_at).toLocaleDateString('el-GR')}
                      </p>
                    </div>
                  </div>
                  {content.access_level === 'download' && (
                    <button
                      onClick={() => handleDownload(doc.id)}
                      className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-blue-500"
                      title="Λήψη"
                    >
                      <Download size={20} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="py-8 text-center text-sm text-gray-400">
          Ασφαλής σύνδεσμος από LogistikoCRM
        </footer>
      </div>
    );
  }

  return null;
}
