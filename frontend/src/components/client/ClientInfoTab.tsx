import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  User,
  Phone,
  Calendar,
  Clock,
  Building,
  Building2,
  MapPin,
  CreditCard,
  Key,
  RefreshCw,
  ExternalLink,
  Save,
  Pencil,
  Shield,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '../../components';
import {
  useClientMyDataCredentials,
  useSaveMyDataCredentials,
  useVerifyMyDataCredentials,
  useSyncMyDataVAT,
} from '../../hooks/useClientDetails';
import type { ClientFull } from '../../types';
import {
  TAXPAYER_TYPES,
  BOOK_CATEGORIES,
  LEGAL_FORMS,
} from '../../types';

// Props interface
export interface ClientInfoTabProps {
  client: ClientFull;
  clientId: number;
  isEditing: boolean;
  onFieldChange: (field: keyof ClientFull, value: unknown) => void;
}

// Field row component
function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="text-sm text-gray-900">{children}</div>
    </div>
  );
}

export default function ClientInfoTab({
  client,
  clientId,
  isEditing,
  onFieldChange,
}: ClientInfoTabProps) {
  // myDATA credentials state
  const [showMyDataForm, setShowMyDataForm] = useState(false);
  const [myDataUserId, setMyDataUserId] = useState('');
  const [myDataSubscriptionKey, setMyDataSubscriptionKey] = useState('');
  const [myDataIsSandbox, setMyDataIsSandbox] = useState(true);

  // myDATA hooks
  const { data: myDataCreds, isLoading: myDataLoading } = useClientMyDataCredentials(clientId);
  const saveMyDataMutation = useSaveMyDataCredentials(clientId);
  const verifyMyDataMutation = useVerifyMyDataCredentials(clientId);
  const syncMyDataMutation = useSyncMyDataVAT(clientId);

  // Initialize form when credentials load
  useEffect(() => {
    if (myDataCreds) {
      setMyDataUserId(myDataCreds.user_id || '');
      setMyDataSubscriptionKey(myDataCreds.subscription_key || '');
      setMyDataIsSandbox(myDataCreds.is_sandbox ?? true);
    }
  }, [myDataCreds]);

  const handleSaveMyDataCredentials = () => {
    saveMyDataMutation.mutate({
      user_id: myDataUserId,
      subscription_key: myDataSubscriptionKey,
      is_sandbox: myDataIsSandbox,
    }, {
      onSuccess: () => setShowMyDataForm(false),
    });
  };

  const handleVerifyMyData = () => {
    if (myDataCreds?.id) {
      verifyMyDataMutation.mutate(myDataCreds.id);
    }
  };

  const handleSyncMyData = () => {
    if (myDataCreds?.id) {
      syncMyDataMutation.mutate({ credentialsId: myDataCreds.id, days: 30 });
    }
  };

  // Helper to get string value from client field
  const getStringValue = (field: keyof ClientFull): string => {
    const value = client[field];
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') return '';
    return String(value);
  };

  const renderField = (
    field: keyof ClientFull,
    type: 'text' | 'email' | 'checkbox' | 'select' | 'date' = 'text',
    options?: { value: string; label: string }[]
  ): React.ReactNode => {
    const value = client[field];
    const stringValue = getStringValue(field);

    if (!isEditing) {
      if (type === 'checkbox') {
        return value ? 'Ναι' : 'Όχι';
      }
      if (type === 'select' && options) {
        const option = options.find((o) => o.value === stringValue);
        return option?.label || stringValue || '-';
      }
      return stringValue || '-';
    }

    if (type === 'checkbox') {
      return (
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onFieldChange(field, e.target.checked)}
          className="h-4 w-4 text-brand-600 rounded border-gray-300 focus:ring-brand-500"
        />
      );
    }

    if (type === 'select' && options) {
      return (
        <select
          value={stringValue}
          onChange={(e) => onFieldChange(field, e.target.value)}
          className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
        >
          <option value="">-- Επιλέξτε --</option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );
    }

    return (
      <input
        type={type}
        value={stringValue}
        onChange={(e) => onFieldChange(field, e.target.value)}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
      />
    );
  };

  return (
    <div className="space-y-8">
      {/* Basic Info Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <User className="w-5 h-5 text-brand-600" />
          Βασικά Στοιχεία
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="Επωνυμία">{renderField('eponimia')}</FieldRow>
          <FieldRow label="ΑΦΜ">{renderField('afm')}</FieldRow>
          <FieldRow label="ΔΟΥ">{renderField('doy')}</FieldRow>
          <FieldRow label="Όνομα">{renderField('onoma')}</FieldRow>
          <FieldRow label="Πατρώνυμο">{renderField('onoma_patros')}</FieldRow>
          <FieldRow label="Ενεργός">{renderField('is_active', 'checkbox')}</FieldRow>
        </div>
      </section>

      {/* Tax Info Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Building className="w-5 h-5 text-green-600" />
          Φορολογικά Στοιχεία
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="Είδος Υπόχρεου">
            {renderField('eidos_ipoxreou', 'select', TAXPAYER_TYPES as unknown as { value: string; label: string }[])}
          </FieldRow>
          <FieldRow label="Κατηγορία Βιβλίων">
            {renderField('katigoria_vivlion', 'select', BOOK_CATEGORIES as unknown as { value: string; label: string }[])}
          </FieldRow>
          <FieldRow label="Νομική Μορφή">
            {renderField('nomiki_morfi', 'select', LEGAL_FORMS as unknown as { value: string; label: string }[])}
          </FieldRow>
          <FieldRow label="Αγρότης">{renderField('agrotis', 'checkbox')}</FieldRow>
          <FieldRow label="Ημερομηνία Έναρξης">
            {renderField('imerominia_enarksis', 'date')}
          </FieldRow>
          <FieldRow label="Αριθμός ΓΕΜΗ">{renderField('arithmos_gemi')}</FieldRow>
        </div>
      </section>

      {/* Contact Info Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Phone className="w-5 h-5 text-purple-600" />
          Στοιχεία Επικοινωνίας
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="Email">{renderField('email', 'email')}</FieldRow>
          <FieldRow label="Κινητό">{renderField('kinito_tilefono')}</FieldRow>
          <FieldRow label="Τηλ. Οικίας 1">{renderField('tilefono_oikias_1')}</FieldRow>
          <FieldRow label="Τηλ. Οικίας 2">{renderField('tilefono_oikias_2')}</FieldRow>
          <FieldRow label="Τηλ. Επιχείρησης 1">{renderField('tilefono_epixeirisis_1')}</FieldRow>
          <FieldRow label="Τηλ. Επιχείρησης 2">{renderField('tilefono_epixeirisis_2')}</FieldRow>
        </div>
      </section>

      {/* Home Address Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <MapPin className="w-5 h-5 text-orange-600" />
          Διεύθυνση Κατοικίας
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="Διεύθυνση">{renderField('diefthinsi_katoikias')}</FieldRow>
          <FieldRow label="Αριθμός">{renderField('arithmos_katoikias')}</FieldRow>
          <FieldRow label="Πόλη">{renderField('poli_katoikias')}</FieldRow>
          <FieldRow label="Δήμος">{renderField('dimos_katoikias')}</FieldRow>
          <FieldRow label="Νομός">{renderField('nomos_katoikias')}</FieldRow>
          <FieldRow label="Τ.Κ.">{renderField('tk_katoikias')}</FieldRow>
        </div>
      </section>

      {/* Business Address Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Building className="w-5 h-5 text-brand-600" />
          Διεύθυνση Επιχείρησης
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="Διεύθυνση">{renderField('diefthinsi_epixeirisis')}</FieldRow>
          <FieldRow label="Αριθμός">{renderField('arithmos_epixeirisis')}</FieldRow>
          <FieldRow label="Πόλη">{renderField('poli_epixeirisis')}</FieldRow>
          <FieldRow label="Δήμος">{renderField('dimos_epixeirisis')}</FieldRow>
          <FieldRow label="Νομός">{renderField('nomos_epixeirisis')}</FieldRow>
          <FieldRow label="Τ.Κ.">{renderField('tk_epixeirisis')}</FieldRow>
        </div>
      </section>

      {/* Bank Info Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <CreditCard className="w-5 h-5 text-green-600" />
          Τραπεζικά Στοιχεία
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldRow label="Τράπεζα">{renderField('trapeza')}</FieldRow>
          <FieldRow label="IBAN">{renderField('iban')}</FieldRow>
        </div>
      </section>

      {/* Credentials Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Key className="w-5 h-5 text-red-600" />
          Διαπιστευτήρια (TAXISnet, ΙΚΑ, ΓΕΜΗ)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FieldRow label="TAXISnet Χρήστης">{renderField('onoma_xristi_taxisnet')}</FieldRow>
          <FieldRow label="TAXISnet Κωδικός">
            {isEditing ? renderField('kodikos_taxisnet') : '••••••••'}
          </FieldRow>
          <FieldRow label="ΙΚΑ Χρήστης">{renderField('onoma_xristi_ika_ergodoti')}</FieldRow>
          <FieldRow label="ΙΚΑ Κωδικός">
            {isEditing ? renderField('kodikos_ika_ergodoti') : '••••••••'}
          </FieldRow>
          <FieldRow label="ΓΕΜΗ Χρήστης">{renderField('onoma_xristi_gemi')}</FieldRow>
          <FieldRow label="ΓΕΜΗ Κωδικός">
            {isEditing ? renderField('kodikos_gemi') : '••••••••'}
          </FieldRow>
        </div>
      </section>

      {/* myDATA ΑΑΔΕ Section */}
      <section>
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Building2 className="w-5 h-5 text-brand-600" />
          myDATA ΑΑΔΕ
          {myDataCreds?.is_verified && (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded bg-green-100 text-green-700">
              <ShieldCheck className="w-3 h-3" />
              Επιβεβαιωμένο
            </span>
          )}
          {myDataCreds && !myDataCreds.is_verified && (
            <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded bg-yellow-100 text-yellow-700">
              <ShieldAlert className="w-3 h-3" />
              Μη επιβεβαιωμένο
            </span>
          )}
        </h3>

        {myDataLoading ? (
          <div className="flex items-center justify-center py-4">
            <RefreshCw className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        ) : myDataCreds && !showMyDataForm ? (
          /* Display existing credentials */
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <FieldRow label="User ID">
                <span className="font-mono">{myDataCreds.user_id}</span>
              </FieldRow>
              <FieldRow label="Subscription Key">
                <span className="font-mono">••••••••{myDataCreds.subscription_key?.slice(-4)}</span>
              </FieldRow>
              <FieldRow label="Περιβάλλον">
                <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                  myDataCreds.is_sandbox
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-green-100 text-green-800'
                }`}>
                  {myDataCreds.is_sandbox ? 'Sandbox (Test)' : 'Production'}
                </span>
              </FieldRow>
              <FieldRow label="Κατάσταση">
                <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                  myDataCreds.is_active
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {myDataCreds.is_active ? 'Ενεργό' : 'Ανενεργό'}
                </span>
              </FieldRow>
              <FieldRow label="Τελευταίο Sync">
                {myDataCreds.last_sync_at
                  ? new Date(myDataCreds.last_sync_at).toLocaleString('el-GR')
                  : 'Ποτέ'}
              </FieldRow>
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowMyDataForm(true)}
              >
                <Pencil className="w-4 h-4 mr-1" />
                Επεξεργασία
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleVerifyMyData}
                disabled={verifyMyDataMutation.isPending}
              >
                {verifyMyDataMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Shield className="w-4 h-4 mr-1" />
                )}
                Επαλήθευση
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleSyncMyData}
                disabled={syncMyDataMutation.isPending || !myDataCreds.is_verified}
                title={!myDataCreds.is_verified ? 'Απαιτείται επαλήθευση credentials' : ''}
              >
                {syncMyDataMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-1" />
                )}
                Sync Δεδομένων
              </Button>
              <Link
                to="/mydata"
                className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded"
              >
                <ExternalLink className="w-4 h-4" />
                Προβολή ΦΠΑ
              </Link>
            </div>

            {/* Verification result */}
            {verifyMyDataMutation.isSuccess && (
              <div className={`p-3 rounded-lg text-sm ${
                verifyMyDataMutation.data.is_verified
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {verifyMyDataMutation.data.is_verified
                  ? 'Τα credentials επαληθεύτηκαν επιτυχώς!'
                  : `Αποτυχία επαλήθευσης: ${verifyMyDataMutation.data.error || 'Άγνωστο σφάλμα'}`}
              </div>
            )}

            {/* Sync result */}
            {syncMyDataMutation.isSuccess && (
              <div className="p-3 bg-green-50 text-green-700 border border-green-200 rounded-lg text-sm">
                Ο συγχρονισμός ολοκληρώθηκε επιτυχώς!
              </div>
            )}
            {syncMyDataMutation.isError && (
              <div className="p-3 bg-red-50 text-red-700 border border-red-200 rounded-lg text-sm">
                Σφάλμα συγχρονισμού: {(syncMyDataMutation.error as Error)?.message || 'Άγνωστο σφάλμα'}
              </div>
            )}
          </div>
        ) : (
          /* Form for new/edit credentials */
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  User ID *
                </label>
                <input
                  type="text"
                  value={myDataUserId}
                  onChange={(e) => setMyDataUserId(e.target.value)}
                  placeholder="Όνομα χρήστη myDATA"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Subscription Key *
                </label>
                <input
                  type="password"
                  value={myDataSubscriptionKey}
                  onChange={(e) => setMyDataSubscriptionKey(e.target.value)}
                  placeholder="Από το myAADE portal"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={myDataIsSandbox}
                  onChange={(e) => setMyDataIsSandbox(e.target.checked)}
                  className="h-4 w-4 text-brand-600 rounded border-gray-300 focus:ring-brand-500"
                />
                <span className="text-sm text-gray-700">
                  Sandbox (Test περιβάλλον)
                </span>
              </label>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleSaveMyDataCredentials}
                disabled={!myDataUserId || !myDataSubscriptionKey || saveMyDataMutation.isPending}
              >
                {saveMyDataMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                Αποθήκευση
              </Button>
              {myDataCreds && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowMyDataForm(false);
                    setMyDataUserId(myDataCreds.user_id || '');
                    setMyDataSubscriptionKey(myDataCreds.subscription_key || '');
                    setMyDataIsSandbox(myDataCreds.is_sandbox ?? true);
                  }}
                >
                  Ακύρωση
                </Button>
              )}
            </div>
            {saveMyDataMutation.isError && (
              <div className="p-3 bg-red-50 text-red-700 border border-red-200 rounded-lg text-sm">
                Σφάλμα αποθήκευσης: {(saveMyDataMutation.error as Error)?.message || 'Άγνωστο σφάλμα'}
              </div>
            )}
            <div className="p-3 bg-brand-50 text-brand-700 border border-brand-200 rounded-lg text-sm">
              <p className="font-medium mb-1">Οδηγίες:</p>
              <ol className="list-decimal list-inside space-y-1 text-xs">
                <li>Συνδεθείτε στο <a href="https://mydata.aade.gr" target="_blank" rel="noopener noreferrer" className="underline">mydata.aade.gr</a></li>
                <li>Πηγαίνετε στο "Διαχείριση Εγγραφής" → "Διαπιστευτήρια"</li>
                <li>Αντιγράψτε το Subscription Key</li>
                <li>Για test χρησιμοποιήστε το Sandbox περιβάλλον</li>
              </ol>
            </div>
          </div>
        )}
      </section>

      {/* Meta Info */}
      <section className="bg-gray-50 rounded-lg p-4">
        <div className="flex flex-wrap gap-6 text-sm text-gray-500">
          <span>
            <Calendar className="w-4 h-4 inline mr-1" />
            Δημιουργία: {new Date(client.created_at).toLocaleDateString('el-GR')}
          </span>
          <span>
            <Clock className="w-4 h-4 inline mr-1" />
            Τελευταία ενημέρωση: {new Date(client.updated_at).toLocaleDateString('el-GR')}
          </span>
        </div>
      </section>
    </div>
  );
}
