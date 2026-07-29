import { useState } from 'react';
import { Copy, Check, Link2, Loader2, X, Upload } from 'lucide-react';
import { Button } from '../../components';
import { useCreateSharedLink } from '../../hooks/useFileManager';
import { DOCUMENT_CATEGORY_GROUPS } from '../../types';
import type { SharedLink } from '../../types/fileManager';

export interface ClientPortalLinkModalProps {
  clientId: number;
  clientName: string;
  onClose: () => void;
}

/**
 * Δημιουργία συνδέσμου portal για πελάτη: ο πελάτης βλέπει τα έγγραφά του
 * και (προαιρετικά) ανεβάζει μόνος του αρχεία που αρχειοθετούνται αυτόματα.
 */
export default function ClientPortalLinkModal({
  clientId,
  clientName,
  onClose,
}: ClientPortalLinkModalProps) {
  const [allowUpload, setAllowUpload] = useState(true);
  const [uploadNote, setUploadNote] = useState('');
  const [uploadCategory, setUploadCategory] = useState('general');
  const [password, setPassword] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<number | null>(30);
  const [createdLink, setCreatedLink] = useState<SharedLink | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const createMutation = useCreateSharedLink();

  const portalUrl = createdLink
    ? `${window.location.origin}/share/${createdLink.token}`
    : '';

  const handleCreate = () => {
    setErrorMessage(null);
    createMutation.mutate(
      {
        client_id: clientId,
        name: `Portal: ${clientName}`,
        access_level: 'download',
        password: password || undefined,
        expires_in_days: expiresInDays,
        allow_upload: allowUpload,
        upload_category: allowUpload ? uploadCategory : undefined,
        upload_note: allowUpload ? uploadNote : undefined,
        // Πεπερασμένο default όριο — προστασία από γέμισμα δίσκου αν διαρρεύσει το link
        max_uploads: allowUpload ? 100 : undefined,
      },
      {
        onSuccess: (link) => setCreatedLink(link),
        onError: () => setErrorMessage('Σφάλμα κατά τη δημιουργία του συνδέσμου'),
      }
    );
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(portalUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: επιλογή κειμένου γίνεται χειροκίνητα
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Link2 className="w-5 h-5 text-blue-500" />
            Portal Πελάτη
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {createdLink ? (
          /* Επιτυχία: εμφάνιση link για αντιγραφή */
          <div className="p-4 space-y-4">
            <p className="text-sm text-gray-600">
              Ο σύνδεσμος δημιουργήθηκε — στείλ' τον στον πελάτη ({clientName}):
            </p>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={portalUrl}
                onFocus={(e) => e.target.select()}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 font-mono"
              />
              <Button onClick={handleCopy}>
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
            {createdLink.allow_upload && (
              <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2.5 flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5 shrink-0" />
                Ο πελάτης μπορεί να ανεβάζει έγγραφα — θα αρχειοθετούνται αυτόματα στον φάκελό του
              </p>
            )}
            <div className="flex justify-end pt-2 border-t">
              <Button variant="secondary" onClick={onClose}>Κλείσιμο</Button>
            </div>
          </div>
        ) : (
          /* Φόρμα δημιουργίας */
          <div className="p-4 space-y-4">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={allowUpload}
                onChange={(e) => setAllowUpload(e.target.checked)}
                className="rounded border-gray-300"
              />
              Ο πελάτης μπορεί να ανεβάζει έγγραφα
            </label>

            {allowUpload && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Οδηγίες προς τον πελάτη (προαιρετικά)
                  </label>
                  <textarea
                    value={uploadNote}
                    onChange={(e) => setUploadNote(e.target.value)}
                    rows={3}
                    placeholder={'Π.χ.\nΧρειαζόμαστε:\n• Τιμολόγια Μαρτίου\n• Κινήσεις τραπέζης'}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Κατηγορία αρχειοθέτησης
                  </label>
                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                  >
                    {DOCUMENT_CATEGORY_GROUPS.map((group) => (
                      <optgroup key={group.label} label={group.label}>
                        {group.categories.map((cat) => (
                          <option key={cat.value} value={cat.value}>{cat.label}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              </>
            )}

            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Κωδικός (προαιρετικά)
                </label>
                <input
                  type="text"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Χωρίς κωδικό"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                />
              </div>
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Λήξη
                </label>
                <select
                  value={expiresInDays ?? ''}
                  onChange={(e) => setExpiresInDays(e.target.value ? parseInt(e.target.value, 10) : null)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                >
                  <option value={7}>7 ημέρες</option>
                  <option value={30}>30 ημέρες</option>
                  <option value={90}>90 ημέρες</option>
                  <option value="">Χωρίς λήξη</option>
                </select>
              </div>
            </div>

            {errorMessage && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-2.5">
                {errorMessage}
              </p>
            )}

            <div className="flex justify-end gap-3 pt-2 border-t">
              <Button variant="secondary" onClick={onClose}>Ακύρωση</Button>
              <Button onClick={handleCreate} disabled={createMutation.isPending}>
                {createMutation.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Link2 className="w-4 h-4 mr-2" />
                )}
                Δημιουργία Συνδέσμου
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
