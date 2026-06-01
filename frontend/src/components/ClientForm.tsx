import { useState, useEffect, type FormEvent } from 'react';
import { Search, Loader2, Check } from 'lucide-react';
import { Button } from './Button';
import { validateAfm, validateAfmChecksum } from '../utils/afm';
import { gsisApi, type AFMData } from '../api/client';
import type { Client, ClientFormData } from '../types';
import { TAXPAYER_TYPES } from '../types';

interface ClientFormProps {
  client?: Client | null;
  onSubmit: (data: ClientFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ClientForm({ client, onSubmit, onCancel, isLoading = false }: ClientFormProps) {
  const [formData, setFormData] = useState<ClientFormData>({
    afm: '',
    eponimia: '',
    eidos_ipoxreou: 'individual',
    email: '',
    kinito_tilefono: '',
    is_active: true,
    // GSIS fields
    doy: '',
    nomiki_morfi: '',
    diefthinsi_epixeirisis: '',
    arithmos_epixeirisis: '',
    poli_epixeirisis: '',
    tk_epixeirisis: '',
    imerominia_enarksis: '',
  });
  const [errors, setErrors] = useState<Partial<Record<keyof ClientFormData, string>>>({});
  const [afmChecksumWarning, setAfmChecksumWarning] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupMessage, setLookupMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [fetchedData, setFetchedData] = useState<AFMData | null>(null);

  // Handle AFM lookup from GSIS
  const handleLookupAfm = async () => {
    if (!formData.afm || formData.afm.length !== 9) {
      setLookupMessage({ type: 'error', text: 'Εισάγετε έγκυρο ΑΦΜ (9 ψηφία)' });
      return;
    }

    setLookupLoading(true);
    setLookupMessage(null);
    setFetchedData(null);

    try {
      const result = await gsisApi.lookupAfm(formData.afm);

      if (result.success && result.data) {
        setFetchedData(result.data);
        // Αυτόματη συμπλήρωση όλων των πεδίων από ΑΑΔΕ
        setFormData(prev => ({
          ...prev,
          eponimia: result.data?.onomasia || prev.eponimia,
          doy: result.data?.doy_descr || prev.doy,
          nomiki_morfi: result.data?.legal_form_descr || prev.nomiki_morfi,
          diefthinsi_epixeirisis: result.data?.postal_address || prev.diefthinsi_epixeirisis,
          arithmos_epixeirisis: result.data?.postal_address_no || prev.arithmos_epixeirisis,
          poli_epixeirisis: result.data?.postal_area || prev.poli_epixeirisis,
          tk_epixeirisis: result.data?.postal_zip_code || prev.tk_epixeirisis,
          imerominia_enarksis: result.data?.registration_date || prev.imerominia_enarksis,
        }));
        setLookupMessage({ type: 'success', text: 'Τα στοιχεία βρέθηκαν και συμπληρώθηκαν!' });
      } else {
        setLookupMessage({ type: 'error', text: result.error || 'Δεν βρέθηκαν στοιχεία' });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Σφάλμα αναζήτησης';
      setLookupMessage({ type: 'error', text: errorMessage });
    } finally {
      setLookupLoading(false);
    }
  };

  // Populate form when editing
  useEffect(() => {
    if (client) {
      setFormData({
        afm: client.afm || '',
        eponimia: client.eponimia || '',
        eidos_ipoxreou: client.eidos_ipoxreou || 'individual',
        email: client.email || '',
        kinito_tilefono: client.kinito_tilefono || '',
        is_active: client.is_active ?? true,
        // GSIS fields
        doy: client.doy || '',
        nomiki_morfi: client.nomiki_morfi || '',
        diefthinsi_epixeirisis: client.diefthinsi_epixeirisis || '',
        arithmos_epixeirisis: client.arithmos_epixeirisis || '',
        poli_epixeirisis: client.poli_epixeirisis || '',
        tk_epixeirisis: client.tk_epixeirisis || '',
        imerominia_enarksis: client.imerominia_enarksis || '',
      });
    }
  }, [client]);

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof ClientFormData, string>> = {};

    if (!formData.eponimia.trim()) {
      newErrors.eponimia = 'Η επωνυμία είναι υποχρεωτική';
    }

    if (!formData.afm.trim()) {
      newErrors.afm = 'Το ΑΦΜ είναι υποχρεωτικό';
    } else if (!validateAfm(formData.afm)) {
      newErrors.afm = 'Μη έγκυρο ΑΦΜ (πρέπει να είναι 9 ψηφία)';
    }

    // Check checksum and set warning (doesn't block submission)
    if (formData.afm && validateAfm(formData.afm)) {
      setAfmChecksumWarning(!validateAfmChecksum(formData.afm));
    }

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Μη έγκυρη διεύθυνση email';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (validate()) {
      // Convert empty date strings to null for Django DateField compatibility
      const dataToSubmit = {
        ...formData,
        imerominia_enarksis: formData.imerominia_enarksis || null,
      };
      onSubmit(dataToSubmit);
    }
  };

  const handleChange = (field: keyof ClientFormData, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Επωνυμία */}
      <div>
        <label htmlFor="eponimia" className="block text-sm font-medium text-gray-700 mb-1">
          Επωνυμία *
        </label>
        <input
          type="text"
          id="eponimia"
          value={formData.eponimia}
          onChange={(e) => handleChange('eponimia', e.target.value)}
          className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
            errors.eponimia ? 'border-red-500' : 'border-gray-300'
          }`}
          placeholder="Εισάγετε επωνυμία"
        />
        {errors.eponimia && <p className="mt-1 text-sm text-red-500">{errors.eponimia}</p>}
      </div>

      {/* Είδος Υπόχρεου */}
      <div>
        <label htmlFor="eidos_ipoxreou" className="block text-sm font-medium text-gray-700 mb-1">
          Είδος Υπόχρεου *
        </label>
        <select
          id="eidos_ipoxreou"
          value={formData.eidos_ipoxreou}
          onChange={(e) => handleChange('eidos_ipoxreou', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {TAXPAYER_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      {/* ΑΦΜ */}
      <div>
        <label htmlFor="afm" className="block text-sm font-medium text-gray-700 mb-1">
          ΑΦΜ *
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            id="afm"
            value={formData.afm}
            onChange={(e) => {
              const newAfm = e.target.value.replace(/\D/g, '').slice(0, 9);
              handleChange('afm', newAfm);
              setLookupMessage(null);
              setFetchedData(null);
              // Check checksum warning in real-time
              if (newAfm.length === 9) {
                setAfmChecksumWarning(!validateAfmChecksum(newAfm));
              } else {
                setAfmChecksumWarning(false);
              }
            }}
            className={`flex-1 px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono ${
              errors.afm ? 'border-red-500' : 'border-gray-300'
            }`}
            placeholder="123456789"
            maxLength={9}
          />
          <Button
            type="button"
            variant="secondary"
            onClick={handleLookupAfm}
            disabled={lookupLoading || formData.afm.length !== 9}
            title="Λήψη στοιχείων από ΑΑΔΕ"
          >
            {lookupLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Search size={18} />
            )}
          </Button>
        </div>
        {errors.afm && <p className="mt-1 text-sm text-red-500">{errors.afm}</p>}
        {!errors.afm && afmChecksumWarning && (
          <p className="mt-1 text-sm text-amber-600">
            ⚠️ Το ΑΦΜ δεν περνάει τον έλεγχο checksum - μπορεί να είναι παλαιό ή ειδικό ΑΦΜ
          </p>
        )}
        {lookupMessage && (
          <p className={`mt-1 text-sm flex items-center gap-1 ${
            lookupMessage.type === 'success' ? 'text-green-600' : 'text-red-500'
          }`}>
            {lookupMessage.type === 'success' && <Check size={14} />}
            {lookupMessage.text}
          </p>
        )}
      </div>

      {/* Fetched Data Preview */}
      {fetchedData && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
          <p className="font-medium text-blue-900 mb-2">Στοιχεία από ΑΑΔΕ:</p>
          <div className="grid grid-cols-2 gap-2 text-blue-800">
            <div>
              <span className="text-blue-600">Επωνυμία:</span> {fetchedData.onomasia}
            </div>
            <div>
              <span className="text-blue-600">ΔΟΥ:</span> {fetchedData.doy_descr}
            </div>
            {fetchedData.postal_address && (
              <div className="col-span-2">
                <span className="text-blue-600">Διεύθυνση:</span>{' '}
                {fetchedData.postal_address} {fetchedData.postal_address_no}, {fetchedData.postal_zip_code} {fetchedData.postal_area}
              </div>
            )}
            {fetchedData.legal_form_descr && (
              <div>
                <span className="text-blue-600">Μορφή:</span> {fetchedData.legal_form_descr}
              </div>
            )}
            {fetchedData.registration_date && (
              <div>
                <span className="text-blue-600">Έναρξη:</span> {fetchedData.registration_date}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          Email
        </label>
        <input
          type="email"
          id="email"
          value={formData.email}
          onChange={(e) => handleChange('email', e.target.value)}
          className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
            errors.email ? 'border-red-500' : 'border-gray-300'
          }`}
          placeholder="example@email.com"
        />
        {errors.email && <p className="mt-1 text-sm text-red-500">{errors.email}</p>}
      </div>

      {/* Τηλέφωνο */}
      <div>
        <label htmlFor="kinito_tilefono" className="block text-sm font-medium text-gray-700 mb-1">
          Κινητό Τηλέφωνο
        </label>
        <input
          type="tel"
          id="kinito_tilefono"
          value={formData.kinito_tilefono}
          onChange={(e) => handleChange('kinito_tilefono', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="69xxxxxxxx"
        />
      </div>

      {/* GSIS Fields Section */}
      {(formData.doy || formData.diefthinsi_epixeirisis || fetchedData) && (
        <div className="border-t border-gray-200 pt-4 mt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Στοιχεία από ΑΑΔΕ</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* ΔΟΥ */}
            <div>
              <label htmlFor="doy" className="block text-sm font-medium text-gray-700 mb-1">
                Δ.Ο.Υ.
              </label>
              <input
                type="text"
                id="doy"
                value={formData.doy}
                onChange={(e) => handleChange('doy', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Δ.Ο.Υ."
              />
            </div>

            {/* Νομική Μορφή */}
            <div>
              <label htmlFor="nomiki_morfi" className="block text-sm font-medium text-gray-700 mb-1">
                Νομική Μορφή
              </label>
              <input
                type="text"
                id="nomiki_morfi"
                value={formData.nomiki_morfi}
                onChange={(e) => handleChange('nomiki_morfi', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Νομική Μορφή"
              />
            </div>

            {/* Διεύθυνση Επιχείρησης */}
            <div>
              <label htmlFor="diefthinsi_epixeirisis" className="block text-sm font-medium text-gray-700 mb-1">
                Διεύθυνση Επιχείρησης
              </label>
              <input
                type="text"
                id="diefthinsi_epixeirisis"
                value={formData.diefthinsi_epixeirisis}
                onChange={(e) => handleChange('diefthinsi_epixeirisis', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Οδός"
              />
            </div>

            {/* Αριθμός */}
            <div>
              <label htmlFor="arithmos_epixeirisis" className="block text-sm font-medium text-gray-700 mb-1">
                Αριθμός
              </label>
              <input
                type="text"
                id="arithmos_epixeirisis"
                value={formData.arithmos_epixeirisis}
                onChange={(e) => handleChange('arithmos_epixeirisis', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Αριθμός"
              />
            </div>

            {/* Πόλη */}
            <div>
              <label htmlFor="poli_epixeirisis" className="block text-sm font-medium text-gray-700 mb-1">
                Πόλη
              </label>
              <input
                type="text"
                id="poli_epixeirisis"
                value={formData.poli_epixeirisis}
                onChange={(e) => handleChange('poli_epixeirisis', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Πόλη"
              />
            </div>

            {/* Τ.Κ. */}
            <div>
              <label htmlFor="tk_epixeirisis" className="block text-sm font-medium text-gray-700 mb-1">
                Τ.Κ.
              </label>
              <input
                type="text"
                id="tk_epixeirisis"
                value={formData.tk_epixeirisis}
                onChange={(e) => handleChange('tk_epixeirisis', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="Τ.Κ."
              />
            </div>

            {/* Ημερομηνία Έναρξης */}
            <div>
              <label htmlFor="imerominia_enarksis" className="block text-sm font-medium text-gray-700 mb-1">
                Ημ/νία Έναρξης
              </label>
              <input
                type="text"
                id="imerominia_enarksis"
                value={formData.imerominia_enarksis ?? ''}
                onChange={(e) => handleChange('imerominia_enarksis', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                placeholder="ΗΗ/ΜΜ/ΕΕΕΕ"
              />
            </div>
          </div>
        </div>
      )}

      {/* Ενεργός */}
      <div className="flex items-center">
        <input
          type="checkbox"
          id="is_active"
          checked={formData.is_active}
          onChange={(e) => handleChange('is_active', e.target.checked)}
          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
        />
        <label htmlFor="is_active" className="ml-2 text-sm text-gray-700">
          Ενεργός πελάτης
        </label>
      </div>

      {/* Buttons */}
      <div className="flex gap-3 pt-4 border-t border-gray-200">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isLoading}>
          Ακύρωση
        </Button>
        <Button type="submit" variant="primary" isLoading={isLoading}>
          {client ? 'Αποθήκευση' : 'Δημιουργία'}
        </Button>
      </div>
    </form>
  );
}

export default ClientForm;
