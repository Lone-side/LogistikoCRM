import { useState } from 'react';
import {
  Bell,
  CheckCircle2,
  Circle,
  ClipboardList,
  Copy,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import {
  useCancelDocumentRequest,
  useCreateDocumentRequest,
  useDocumentRequests,
  useMarkRequestItem,
  useSendRequestReminder,
} from '../../hooks/useFileManager';
import type { DocumentRequest } from '../../types/fileManager';
import { DOCUMENT_CATEGORY_GROUPS } from '../../types';

function portalUrl(request: DocumentRequest): string | null {
  if (!request.shared_link) return null;
  return `${window.location.origin}/share/${request.shared_link.token}`;
}

function RequestCard({ request }: { request: DocumentRequest }) {
  const sendReminder = useSendRequestReminder();
  const markItem = useMarkRequestItem();
  const cancelRequest = useCancelDocumentRequest();
  const [message, setMessage] = useState<string | null>(null);

  const link = request.shared_link;
  const linkExpired = !!link && !link.is_valid;
  const url = portalUrl(request);

  const handleReminder = async () => {
    setMessage(null);
    try {
      await sendReminder.mutateAsync(request.id);
      setMessage('✅ Η υπενθύμιση στάλθηκε');
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setMessage(detail || 'Αποτυχία αποστολής υπενθύμισης');
    }
  };

  const handleCopy = async () => {
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setMessage('Ο σύνδεσμος αντιγράφηκε');
  };

  const handleCancel = async () => {
    if (!window.confirm(`Ακύρωση του αιτήματος «${request.title}»;`)) return;
    await cancelRequest.mutateAsync(request.id);
  };

  const statusBadge = {
    open: ['bg-warning-100 text-warning-700', 'Ανοιχτό'],
    completed: ['bg-success-100 text-success-700', 'Ολοκληρώθηκε'],
    cancelled: ['bg-slate-100 text-slate-500', 'Ακυρώθηκε'],
  }[request.status];

  return (
    <div className="border border-slate-200 rounded-lg p-3 bg-white">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{request.title}</span>
            <span className={`px-2 py-0.5 rounded-full text-xs ${statusBadge[0]}`}>
              {statusBadge[1]}
            </span>
            {linkExpired && request.status === 'open' && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-danger-100 text-danger-700">
                Ο σύνδεσμος έληξε
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {request.received_count}/{request.total_count} ελήφθησαν
            {request.reminder_count > 0 &&
              ` · Υπενθυμίσεις: ${request.reminder_count}/${request.max_reminders}`}
            {request.due_date &&
              ` · Προθεσμία: ${new Date(request.due_date).toLocaleDateString('el-GR')}`}
          </p>
        </div>
        {request.status === 'open' && (
          <div className="flex gap-1 flex-shrink-0">
            {url && (
              <button
                onClick={handleCopy}
                title="Αντιγραφή συνδέσμου"
                aria-label="Αντιγραφή συνδέσμου"
                className="p-1.5 rounded hover:bg-slate-100 text-slate-500"
              >
                <Copy className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={handleReminder}
              disabled={sendReminder.isPending || linkExpired}
              title="Αποστολή υπενθύμισης"
              aria-label="Αποστολή υπενθύμισης"
              className="p-1.5 rounded hover:bg-slate-100 text-slate-500 disabled:opacity-40"
            >
              <Bell className="w-4 h-4" />
            </button>
            <button
              onClick={handleCancel}
              title="Ακύρωση αιτήματος"
              aria-label="Ακύρωση αιτήματος"
              className="p-1.5 rounded hover:bg-danger-50 text-danger-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {request.status !== 'cancelled' && (
        <ul className="mt-2 space-y-1">
          {request.items.map((item) => (
            <li key={item.id} className="flex items-center gap-2 text-sm">
              <button
                onClick={() =>
                  markItem.mutate({
                    requestId: request.id,
                    itemId: item.id,
                    isReceived: !item.is_received,
                  })
                }
                title={item.is_received ? 'Σήμανση ως μη παραληφθέν' : 'Σήμανση ως παραληφθέν'}
                className="flex-shrink-0"
              >
                {item.is_received ? (
                  <CheckCircle2 className="w-4 h-4 text-success-600" />
                ) : (
                  <Circle className="w-4 h-4 text-slate-300 hover:text-slate-400" />
                )}
              </button>
              <span className={item.is_received ? 'text-slate-400 line-through' : 'text-slate-700'}>
                {item.label}
              </span>
            </li>
          ))}
        </ul>
      )}

      {message && <p className="text-xs text-slate-600 mt-2">{message}</p>}
    </div>
  );
}

export function DocumentRequestModal({
  clientId,
  clientName,
  onClose,
}: {
  clientId: number;
  clientName: string;
  onClose: () => void;
}) {
  const createRequest = useCreateDocumentRequest();
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [expiresInDays, setExpiresInDays] = useState(30);
  const [password, setPassword] = useState('');
  const [items, setItems] = useState<Array<{ label: string; category: string }>>([
    { label: '', category: '' },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ url: string | null; emailSent: boolean } | null>(null);

  const setItem = (index: number, patch: Partial<{ label: string; category: string }>) => {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  };

  const handleCreate = async () => {
    setError(null);
    const cleanItems = items
      .map((it) => ({ label: it.label.trim(), category: it.category }))
      .filter((it) => it.label);
    if (!title.trim() || cleanItems.length === 0) {
      setError('Συμπλήρωσε τίτλο και τουλάχιστον ένα ζητούμενο έγγραφο');
      return;
    }
    try {
      const result = await createRequest.mutateAsync({
        client_id: clientId,
        title: title.trim(),
        notes: notes.trim(),
        due_date: dueDate || null,
        items: cleanItems,
        expires_in_days: expiresInDays,
        password: password || undefined,
      });
      setCreated({
        url: result.shared_link
          ? `${window.location.origin}/share/${result.shared_link.token}`
          : null,
        emailSent: result.email_sent,
      });
    } catch (e: unknown) {
      const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data;
      setError(data ? JSON.stringify(data) : 'Σφάλμα δημιουργίας αιτήματος');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="font-semibold">Αίτημα εγγράφων — {clientName}</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-100">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        {created ? (
          <div className="p-5 space-y-3">
            <p className="text-success-700 font-medium">✅ Το αίτημα δημιουργήθηκε</p>
            {created.emailSent ? (
              <p className="text-sm text-slate-600">
                Στάλθηκε email στον πελάτη με τον σύνδεσμο του portal.
              </p>
            ) : (
              <p className="text-sm text-orange-700">
                Ο πελάτης δεν έχει email — αντίγραψε τον σύνδεσμο και στείλ'τον χειροκίνητα.
              </p>
            )}
            {created.url && (
              <div className="flex items-center gap-2 bg-slate-50 rounded-lg p-2">
                <code className="text-xs flex-1 truncate">{created.url}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(created.url!)}
                  className="p-1.5 rounded hover:bg-slate-200"
                  title="Αντιγραφή"
                  aria-label="Αντιγραφή"
                >
                  <Copy className="w-4 h-4 text-slate-500" />
                </button>
              </div>
            )}
            <button
              onClick={onClose}
              className="w-full bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700"
            >
              Κλείσιμο
            </button>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            <div>
              <label htmlFor="docreq-title" className="block text-sm font-medium text-slate-700 mb-1">Τίτλος *</label>
              <input
                id="docreq-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="π.χ. Δικαιολογητικά ΦΠΑ Ιουλίου"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>

            <div>
              <span
                id="docreq-items-label"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Ζητούμενα έγγραφα *
              </span>
              <div className="space-y-2" role="group" aria-labelledby="docreq-items-label">
                {items.map((item, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      value={item.label}
                      onChange={(e) => setItem(i, { label: e.target.value })}
                      placeholder={`Έγγραφο ${i + 1} — π.χ. Τιμολόγια αγορών`}
                      className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm"
                    />
                    <select
                      value={item.category}
                      onChange={(e) => setItem(i, { category: e.target.value })}
                      className="border border-slate-300 rounded-lg px-2 py-2 text-sm w-36"
                    >
                      <option value="">Κατηγορία…</option>
                      {DOCUMENT_CATEGORY_GROUPS.map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.categories.map((cat) => (
                            <option key={cat.value} value={cat.value}>{cat.label}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    {items.length > 1 && (
                      <button
                        onClick={() => setItems((prev) => prev.filter((_, j) => j !== i))}
                        className="p-2 text-slate-400 hover:text-danger-600"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={() => setItems((prev) => [...prev, { label: '', category: '' }])}
                className="mt-2 flex items-center gap-1 text-sm text-brand-600 hover:underline"
              >
                <Plus className="w-4 h-4" /> Προσθήκη εγγράφου
              </button>
            </div>

            <div>
              <label htmlFor="docreq-notes" className="block text-sm font-medium text-slate-700 mb-1">Σημειώσεις</label>
              <textarea
                id="docreq-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="docreq-due-date" className="block text-sm font-medium text-slate-700 mb-1">Προθεσμία</label>
                <input
                  id="docreq-due-date"
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-2 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="docreq-expiry" className="block text-sm font-medium text-slate-700 mb-1">
                  Λήξη link (μέρες)
                </label>
                <input
                  id="docreq-expiry"
                  type="number"
                  min={1}
                  max={365}
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(Number(e.target.value) || 30)}
                  className="w-full border border-slate-300 rounded-lg px-2 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="docreq-password" className="block text-sm font-medium text-slate-700 mb-1">Κωδικός</label>
                <input
                  id="docreq-password"
                  type="text"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Προαιρετικός"
                  className="w-full border border-slate-300 rounded-lg px-2 py-2 text-sm"
                />
              </div>
            </div>

            {error && <p className="text-sm text-danger-600">{error}</p>}

            <button
              onClick={handleCreate}
              disabled={createRequest.isPending}
              className="w-full bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {createRequest.isPending ? 'Δημιουργία…' : 'Δημιουργία & αποστολή στον πελάτη'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DocumentRequestsSection({
  clientId,
  clientName,
}: {
  clientId: number;
  clientName: string;
}) {
  const { data: requests, isLoading } = useDocumentRequests(clientId);
  const [modalOpen, setModalOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const visible = (requests || []).filter(
    (r) => showAll || r.status === 'open'
  );
  const openCount = (requests || []).filter((r) => r.status === 'open').length;

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-slate-500" />
          <h4 className="text-sm font-medium text-slate-700">
            Αιτήματα εγγράφων {openCount > 0 && `(${openCount} ανοιχτά)`}
          </h4>
        </div>
        <div className="flex gap-2">
          {(requests || []).length > openCount && (
            <button
              onClick={() => setShowAll((v) => !v)}
              className="text-xs text-slate-500 hover:underline"
            >
              {showAll ? 'Μόνο ανοιχτά' : 'Όλα'}
            </button>
          )}
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1 text-sm text-brand-600 hover:underline"
          >
            <Plus className="w-4 h-4" /> Νέο αίτημα
          </button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-xs text-slate-400">Φόρτωση…</p>
      ) : visible.length === 0 ? (
        <p className="text-xs text-slate-400">
          Κανένα {showAll ? '' : 'ανοιχτό '}αίτημα — ζήτησε συγκεκριμένα έγγραφα από τον
          πελάτη με ένα κλικ.
        </p>
      ) : (
        <div className="space-y-2">
          {visible.map((request) => (
            <RequestCard key={request.id} request={request} />
          ))}
        </div>
      )}

      {modalOpen && (
        <DocumentRequestModal
          clientId={clientId}
          clientName={clientName}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
