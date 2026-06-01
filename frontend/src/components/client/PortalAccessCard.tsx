import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { KeyRound, ShieldCheck, ShieldAlert, Mail, AlertTriangle, Send } from 'lucide-react';
import { clientsApi } from '../../api/client';
import { Button } from '../../components';

interface Props {
  clientId: number;
}

/**
 * Staff-only card to manage a client's portal access — create the account,
 * (re)send the set-password invite. So the accountant never needs the Django
 * admin for this.
 */
export function PortalAccessCard({ clientId }: Props) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string>('');

  const { data: status, isLoading, isError } = useQuery({
    queryKey: ['portal-status', clientId],
    queryFn: () => clientsApi.getPortalStatus(clientId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['portal-status', clientId] });

  const createMutation = useMutation({
    mutationFn: () => clientsApi.createPortalAccount(clientId),
    onSuccess: (data) => {
      setMessage(data.detail || 'Ο λογαριασμός δημιουργήθηκε.');
      invalidate();
    },
    onError: () => setMessage('Σφάλμα κατά τη δημιουργία λογαριασμού.'),
  });

  const resendMutation = useMutation({
    mutationFn: () => clientsApi.resendPortalInvite(clientId),
    onSuccess: (data) => setMessage(data.detail || 'Η πρόσκληση στάλθηκε ξανά.'),
    onError: () => setMessage('Σφάλμα κατά την αποστολή πρόσκλησης.'),
  });

  const busy = createMutation.isPending || resendMutation.isPending;

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-4" aria-label="Πρόσβαση Πύλης Πελάτη">
      <div className="flex items-center gap-2 mb-3">
        <KeyRound className="w-5 h-5 text-blue-600" aria-hidden="true" />
        <h3 className="font-semibold text-gray-900">Πρόσβαση Πύλης Πελάτη</h3>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500">Φόρτωση…</p>
      ) : isError || !status ? (
        <p className="text-sm text-red-700">Σφάλμα φόρτωσης κατάστασης.</p>
      ) : (
        <div className="space-y-3">
          {/* Status row */}
          {status.has_portal_account ? (
            <div className="flex items-center gap-2 text-sm">
              <ShieldCheck className="w-4 h-4 text-green-600" aria-hidden="true" />
              <span className="text-gray-700">Ενεργός λογαριασμός · χρήστης:</span>
              <code className="px-1.5 py-0.5 bg-gray-100 rounded">{status.portal_username}</code>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm">
              <ShieldAlert className="w-4 h-4 text-gray-400" aria-hidden="true" />
              <span className="text-gray-600">Χωρίς πρόσβαση — δεν έχει λογαριασμό portal.</span>
            </div>
          )}

          {/* Email warning */}
          {!status.has_email && (
            <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
              <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Ο πελάτης είναι χωρίς email — η πρόσκληση δεν μπορεί να σταλεί αυτόματα.</span>
            </div>
          )}
          {status.has_email && (
            <p className="flex items-center gap-1.5 text-xs text-gray-500">
              <Mail className="w-3.5 h-3.5" aria-hidden="true" /> {status.email}
            </p>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            {!status.has_portal_account ? (
              <Button onClick={() => createMutation.mutate()} disabled={busy}>
                <KeyRound className="w-4 h-4 mr-2" />
                {createMutation.isPending ? 'Δημιουργία…' : 'Δημιουργία λογαριασμού & πρόσκληση'}
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => resendMutation.mutate()}
                disabled={busy}
              >
                <Send className="w-4 h-4 mr-2" />
                {resendMutation.isPending ? 'Αποστολή…' : 'Επαναποστολή πρόσκλησης'}
              </Button>
            )}
          </div>

          {/* Feedback */}
          {message && (
            <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-md p-2">
              {message}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
