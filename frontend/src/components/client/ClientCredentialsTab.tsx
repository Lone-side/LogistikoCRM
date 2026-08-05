import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Key,
  Eye,
  EyeOff,
  Copy,
  Check,
  Plus,
  Pencil,
  Trash2,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '../../components';
import { EmptyState, Input, Select } from '../ui';
import { clientCredentialsApi } from '../../api/client';
import type { ClientCredential } from '../../types';
import { CREDENTIAL_SERVICE_OPTIONS } from '../../types';

const REVEAL_HIDE_SECONDS = 30;

interface ClientCredentialsTabProps {
  clientId: number;
}

interface FormState {
  id: number | null;
  service: string;
  label: string;
  username: string;
  secret: string;
}

const EMPTY_FORM: FormState = { id: null, service: 'TAXISNET', label: '', username: '', secret: '' };

export default function ClientCredentialsTab({ clientId }: ClientCredentialsTabProps) {
  const [credentials, setCredentials] = useState<ClientCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Record<number, string>>({});
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const hideTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await clientCredentialsApi.list(clientId);
      setCredentials(Array.isArray(data) ? data : data.results ?? []);
      setForbidden(false);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403 || status === 404) {
        setForbidden(true);
      } else {
        setError('Σφάλμα φόρτωσης κωδικών.');
      }
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    load();
    const timers = hideTimers.current;
    return () => Object.values(timers).forEach(clearTimeout);
  }, [load]);

  const handleReveal = async (cred: ClientCredential) => {
    if (revealed[cred.id] !== undefined) {
      clearTimeout(hideTimers.current[cred.id]);
      setRevealed((prev) => {
        const next = { ...prev };
        delete next[cred.id];
        return next;
      });
      return;
    }
    try {
      const { secret } = await clientCredentialsApi.reveal(clientId, cred.id);
      setRevealed((prev) => ({ ...prev, [cred.id]: secret }));
      // Αυτόματη απόκρυψη μετά από 30"
      hideTimers.current[cred.id] = setTimeout(() => {
        setRevealed((prev) => {
          const next = { ...prev };
          delete next[cred.id];
          return next;
        });
      }, REVEAL_HIDE_SECONDS * 1000);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 403
          ? 'Δεν έχετε δικαίωμα αποκάλυψης κωδικών.'
          : status === 429
            ? 'Υπερβήκατε το όριο αποκαλύψεων (10/ώρα). Δοκιμάστε αργότερα.'
            : status === 500
              ? 'Αποτυχία αποκρυπτογράφησης — ειδοποιήστε τον διαχειριστή.'
              : 'Σφάλμα κατά την αποκάλυψη κωδικού.'
      );
    }
  };

  const handleCopy = async (id: number) => {
    const secret = revealed[id];
    if (secret === undefined) return;
    await navigator.clipboard.writeText(secret);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        service: form.service,
        label: form.label,
        username: form.username,
        ...(form.secret ? { secret: form.secret } : {}),
      };
      if (form.id === null) {
        await clientCredentialsApi.create(clientId, payload);
      } else {
        await clientCredentialsApi.update(clientId, form.id, payload);
      }
      setForm(null);
      await load();
    } catch {
      setError('Σφάλμα αποθήκευσης. Ελέγξτε ότι δεν υπάρχει ήδη εγγραφή για την ίδια υπηρεσία/ετικέτα.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (cred: ClientCredential) => {
    if (!window.confirm(`Διαγραφή κωδικού ${cred.service_display};`)) return;
    try {
      await clientCredentialsApi.remove(clientId, cred.id);
      await load();
    } catch {
      setError('Σφάλμα διαγραφής.');
    }
  };

  if (forbidden) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Χωρίς πρόσβαση"
        description="Δεν έχετε δικαίωμα προβολής των κωδικών αυτού του πελάτη."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Key className="w-5 h-5 text-danger-600" />
          Κωδικοί Υπηρεσιών (Taxisnet, ΕΦΚΑ, ΓΕΜΗ)
        </h3>
        <Button size="sm" onClick={() => setForm({ ...EMPTY_FORM })}>
          <Plus className="w-4 h-4 mr-1" />
          Νέος κωδικός
        </Button>
      </div>

      <p className="text-sm text-slate-500">
        Οι κωδικοί αποθηκεύονται κρυπτογραφημένοι. Κάθε αποκάλυψη καταγράφεται
        και ο κωδικός κρύβεται ξανά αυτόματα μετά από {REVEAL_HIDE_SECONDS}″.
      </p>

      {error && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-4 py-3 text-sm text-danger-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-slate-500 py-8 text-center">Φόρτωση…</div>
      ) : credentials.length === 0 && !form ? (
        <EmptyState
          icon={Key}
          title="Δεν υπάρχουν κωδικοί"
          description="Προσθέστε τους κωδικούς του πελάτη για Taxisnet, ΕΦΚΑ ή ΓΕΜΗ."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                <th className="py-2 pr-4">Υπηρεσία</th>
                <th className="py-2 pr-4">Ετικέτα</th>
                <th className="py-2 pr-4">Όνομα χρήστη</th>
                <th className="py-2 pr-4">Κωδικός</th>
                <th className="py-2 pr-4 text-right">Ενέργειες</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {credentials.map((cred) => {
                const secret = revealed[cred.id];
                const isRevealed = secret !== undefined;
                return (
                  <tr key={cred.id}>
                    <td className="py-3 pr-4 font-medium text-slate-900">{cred.service_display}</td>
                    <td className="py-3 pr-4 text-slate-600">{cred.label || '—'}</td>
                    <td className="py-3 pr-4 font-mono text-slate-700">{cred.username || '—'}</td>
                    <td className="py-3 pr-4">
                      {cred.has_secret ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="font-mono text-slate-700">
                            {isRevealed ? secret : cred.secret_masked}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleReveal(cred)}
                            className="p-1 rounded hover:bg-slate-100 text-slate-500"
                            aria-label={isRevealed ? 'Απόκρυψη κωδικού' : 'Εμφάνιση κωδικού'}
                            title={isRevealed ? 'Απόκρυψη' : 'Εμφάνιση'}
                          >
                            {isRevealed ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                          {isRevealed && (
                            <button
                              type="button"
                              onClick={() => handleCopy(cred.id)}
                              className="p-1 rounded hover:bg-slate-100 text-slate-500"
                              aria-label="Αντιγραφή κωδικού"
                              title="Αντιγραφή"
                            >
                              {copiedId === cred.id ? (
                                <Check className="w-4 h-4 text-success-600" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() =>
                            setForm({
                              id: cred.id,
                              service: cred.service,
                              label: cred.label,
                              username: cred.username,
                              secret: '',
                            })
                          }
                          className="p-1.5 rounded hover:bg-slate-100 text-slate-500"
                          aria-label="Επεξεργασία"
                          title="Επεξεργασία"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(cred)}
                          className="p-1.5 rounded hover:bg-danger-50 text-danger-500"
                          aria-label="Διαγραφή"
                          title="Διαγραφή"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {form && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-4">
          <h4 className="font-semibold text-slate-900">
            {form.id === null ? 'Νέος κωδικός' : 'Επεξεργασία κωδικού'}
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Υπηρεσία"
              value={form.service}
              onChange={(e) => setForm({ ...form, service: e.target.value })}
            >
              {CREDENTIAL_SERVICE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            <Input
              label="Ετικέτα (προαιρετικό)"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="π.χ. Υποκατάστημα"
            />
            <Input
              label="Όνομα χρήστη"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              autoComplete="off"
            />
            <Input
              label={form.id === null ? 'Κωδικός' : 'Νέος κωδικός (κενό = χωρίς αλλαγή)'}
              type="password"
              value={form.secret}
              onChange={(e) => setForm({ ...form, secret: e.target.value })}
              autoComplete="new-password"
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? 'Αποθήκευση…' : 'Αποθήκευση'}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setForm(null)}>
              Ακύρωση
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
