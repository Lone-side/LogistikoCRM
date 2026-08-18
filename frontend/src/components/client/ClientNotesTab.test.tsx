/**
 * Οι «Σημειώσεις Πελάτη» δεν έχουν backend.
 *
 * ΤΟ ΣΦΑΛΜΑ ΠΟΥ ΚΛΕΙΔΩΝΕΙ ΕΔΩ: σε λειτουργία επεξεργασίας εμφανιζόταν
 * textarea. Το κείμενο πήγαινε σε τοπικό useState, καμία κλήση API — ο
 * χρήστης πατούσε «Αποθήκευση», δεν έβλεπε σφάλμα, και το κείμενο χανόταν
 * στο επόμενο refresh. Επιβεβαιώθηκε σε πραγματικό browser.
 *
 * Όσο δεν υπάρχει πεδίο στο backend, η καρτέλα ΔΕΝ επιτρέπεται να δείχνει
 * στοιχείο εισαγωγής. Αν κάποιος υλοποιήσει τις σημειώσεις, αυτό το test
 * θα κοκκινίσει και πρέπει να αντικατασταθεί με έλεγχο αποθήκευσης.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ClientNotesTab from './ClientNotesTab';
import type { ClientFull } from '../../types';

const CLIENT = { id: 1, afm: '148200002', eponimia: 'ΔΟΚΙΜΗ Α.Ε.' } as ClientFull;

function renderTab(isEditing: boolean) {
  return render(
    <ClientNotesTab client={CLIENT} isEditing={isEditing} onFieldChange={vi.fn()} />
  );
}

describe('ClientNotesTab', () => {
  it('δεν δείχνει πεδίο εισαγωγής σε λειτουργία επεξεργασίας', () => {
    const { container } = renderTab(true);

    expect(container.querySelector('textarea')).toBeNull();
    expect(container.querySelector('input')).toBeNull();
  });

  it('δεν δείχνει πεδίο εισαγωγής ούτε σε λειτουργία προβολής', () => {
    const { container } = renderTab(false);

    expect(container.querySelector('textarea')).toBeNull();
  });

  it('λέει καθαρά ότι η λειτουργία δεν είναι διαθέσιμη', () => {
    renderTab(true);

    expect(screen.getByText(/θα προστεθεί σύντομα/)).toBeInTheDocument();
  });
});
