import type { FC } from 'react';
import type { ClientFull } from '../../types';

// Props interface
export interface ClientNotesTabProps {
  client: ClientFull;
  isEditing: boolean;
  onFieldChange: (field: keyof ClientFull, value: unknown) => void;
}

/**
 * Σημειώσεις πελάτη — ΔΕΝ ΕΧΕΙ ΥΛΟΠΟΙΗΘΕΙ ΑΚΟΜΑ.
 *
 * Δεν υπάρχει πεδίο/μοντέλο για σημειώσεις πελάτη στο backend, οπότε δεν
 * υπάρχει πουθενά να αποθηκευτούν.
 *
 * ΓΙΑΤΙ ΔΕΝ ΔΕΙΧΝΕΙ ΠΛΕΟΝ textarea ΣΕ ΛΕΙΤΟΥΡΓΙΑ ΕΠΕΞΕΡΓΑΣΙΑΣ: έδειχνε.
 * Το κείμενο έμπαινε σε τοπικό useState και δεν έφευγε ποτέ προς το API.
 * Ο χρήστης έγραφε σημειώσεις, πατούσε «Αποθήκευση», δεν έπαιρνε κανένα
 * σφάλμα — και τα έχανε στο πρώτο refresh. Μέχρι να υπάρξει backend, το
 * σωστό είναι να μην υπόσχεται η οθόνη κάτι που δεν κάνει.
 */
// Τα props μένουν στην υπογραφή γιατί το ClientDetails τα περνά· δεν
// χρησιμοποιούνται όσο δεν υπάρχει backend να γράψει.
const ClientNotesTab: FC<ClientNotesTabProps> = () => {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-slate-700">Σημειώσεις Πελάτη</h3>
      <div className="bg-slate-50 rounded-lg p-4 min-h-[200px]">
        <p className="text-slate-400 italic">
          Δεν υπάρχουν σημειώσεις. Η λειτουργία αυτή θα προστεθεί σύντομα.
        </p>
      </div>
    </div>
  );
};

export default ClientNotesTab;
