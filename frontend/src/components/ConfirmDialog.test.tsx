import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from './ConfirmDialog';

const baseProps = {
  isOpen: true,
  onClose: vi.fn(),
  onConfirm: vi.fn(),
  title: 'Διαγραφή Υποχρεώσεων',
  message: 'Η ενέργεια δεν αναιρείται.',
  confirmText: 'Διαγραφή',
};

const confirmButton = () => screen.getByRole('button', { name: 'Διαγραφή' });

describe('ConfirmDialog', () => {
  it('επιβεβαιώνει κανονικά όταν δεν ζητείται πληκτρολόγηση', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...baseProps} onConfirm={onConfirm} />);

    expect(confirmButton()).toBeEnabled();
    fireEvent.click(confirmButton());
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('κρατά το κουμπί ανενεργό μέχρι να πληκτρολογηθεί η ακριβής τιμή', () => {
    render(<ConfirmDialog {...baseProps} requireTypedConfirmation="12" />);

    expect(confirmButton()).toBeDisabled();

    const input = screen.getByRole('textbox');
    // Μερική ή λάθος τιμή δεν ξεκλειδώνει.
    fireEvent.change(input, { target: { value: '1' } });
    expect(confirmButton()).toBeDisabled();
    fireEvent.change(input, { target: { value: '123' } });
    expect(confirmButton()).toBeDisabled();

    fireEvent.change(input, { target: { value: '12' } });
    expect(confirmButton()).toBeEnabled();
  });

  it('μηδενίζει το πληκτρολογημένο κείμενο όταν ο διάλογος ξανανοίγει', () => {
    // Regression: το σώμα ζει μέσα στο Modal, που κάνει unmount όταν κλείνει.
    // Αν κάποιος ανεβάσει ξανά το state πιο πάνω, μια «οπλισμένη» επιβεβαίωση
    // θα επιβίωνε στο επόμενο άνοιγμα — ακριβώς ό,τι δεν θέλουμε σε μαζική
    // διαγραφή.
    const { rerender } = render(
      <ConfirmDialog {...baseProps} requireTypedConfirmation="12" />
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '12' } });
    expect(confirmButton()).toBeEnabled();

    rerender(<ConfirmDialog {...baseProps} isOpen={false} requireTypedConfirmation="12" />);
    rerender(<ConfirmDialog {...baseProps} isOpen={true} requireTypedConfirmation="12" />);

    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(confirmButton()).toBeDisabled();
  });

  it('δεν αποδέχεται τιμή που ταιριάζει σε άλλο πλήθος', () => {
    // Το πλήθος αλλάζει όταν ο χρήστης αλλάξει επιλογή· η παλιά τιμή δεν
    // πρέπει να ξεκλειδώνει τη νέα διαγραφή.
    const { rerender } = render(
      <ConfirmDialog {...baseProps} requireTypedConfirmation="3" />
    );

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '3' } });
    expect(confirmButton()).toBeEnabled();

    rerender(<ConfirmDialog {...baseProps} requireTypedConfirmation="30" />);
    expect(confirmButton()).toBeDisabled();
  });

  it('δείχνει το προεπιλεγμένο ελληνικό label και το τιμά το custom', () => {
    const { rerender } = render(
      <ConfirmDialog {...baseProps} requireTypedConfirmation="7" />
    );
    expect(
      screen.getByText('Πληκτρολόγησε "7" για επιβεβαίωση')
    ).toBeInTheDocument();

    rerender(
      <ConfirmDialog
        {...baseProps}
        requireTypedConfirmation="7"
        typedConfirmationLabel="Γράψε τον αριθμό 7"
      />
    );
    expect(screen.getByText('Γράψε τον αριθμό 7')).toBeInTheDocument();
  });

  it('δεν εμφανίζει πεδίο όταν δεν ζητείται πληκτρολόγηση', () => {
    render(<ConfirmDialog {...baseProps} />);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('δεν αποδίδει τίποτα όταν είναι κλειστός', () => {
    render(<ConfirmDialog {...baseProps} isOpen={false} />);
    expect(screen.queryByText('Η ενέργεια δεν αναιρείται.')).not.toBeInTheDocument();
  });

  it('κλειδώνει την επιβεβαίωση όσο εκτελείται η ενέργεια', () => {
    // Το isPending υπερισχύει του isLoading, και το Button αντικαθιστά το
    // κείμενο με «Φόρτωση...» όταν φορτώνει.
    render(<ConfirmDialog {...baseProps} isPending requireTypedConfirmation="12" />);

    const loading = screen.getByRole('button', { name: /Φόρτωση/ });
    expect(loading).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Ακύρωση' })).toBeDisabled();
  });

  it('καλεί το onClose από το κουμπί ακύρωσης', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...baseProps} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'Ακύρωση' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
