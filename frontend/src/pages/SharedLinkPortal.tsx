/**
 * SharedLinkPortal.tsx
 * Public page for accessing shared files/folders (no authentication required)
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  File, FileText, FileSpreadsheet, Image, Download, Lock, Mail,
  AlertCircle, Loader2, FolderOpen
} from 'lucide-react';
import { Button } from '../components/Button';
import apiClient from '../api/client';
import type { PublicSharedContent } from '../types/fileManager';

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
  useEffect(() => {
    if (!token) {
      setError('Μη έγκυρος σύνδεσμος');
      setLoading(false);
      return;
    }

    const fetchSharedContent = async () => {
      try {
        const response = await apiClient.get(`/accounting/share/${token}/`);
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
      } catch (err: any) {
        if (err.response?.status === 410) {
          setError(err.response?.data?.error || 'Ο σύνδεσμος δεν είναι πλέον διαθέσιμος');
        } else {
          setError('Σφάλμα κατά τη φόρτωση');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchSharedContent();
  }, [token]);

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
      const response = await apiClient.post(`/accounting/share/${token}/`, {
        password: needsPassword ? password : undefined,
        email: needsEmail ? email : undefined,
      });
      setContent(response.data);
      setRequiresAuth(false);
    } catch (err: any) {
      setAuthError(err.response?.data?.error || 'Σφάλμα επαλήθευσης');
    } finally {
      setAuthenticating(false);
    }
  };

  // Handle download
  const handleDownload = async (docId?: number) => {
    try {
      const downloadUrl = docId
        ? `/accounting/share/${token}/download/?doc_id=${docId}`
        : `/accounting/share/${token}/download/`;

      window.open(downloadUrl, '_blank');
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
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Κωδικός πρόσβασης
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
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
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input
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
