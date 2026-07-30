import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyDataInvoices from './MyDataInvoices';
import type { MyDataInvoice } from '../api/client';

const { mockGetAll, mockSend, mockCancel } = vi.hoisted(() => ({
  mockGetAll: vi.fn(),
  mockSend: vi.fn(),
  mockCancel: vi.fn(),
}));

vi.mock('../api/client', () => ({
  mydataApi: {
    invoices: {
      getAll: mockGetAll,
      send: mockSend,
      cancel: mockCancel,
    },
  },
}));

function makeInvoice(overrides: Partial<MyDataInvoice> = {}): MyDataInvoice {
  return {
    id: 1,
    series: 'Α',
    number: '101',
    invoice_type: '2.1',
    invoice_type_display: 'Τιμολόγιο Παροχής Υπηρεσιών',
    issue_date: '2026-07-30',
    counterpart_name: 'ΠΕΛΑΤΗΣ ΑΕ',
    counterpart_vat: '123456783',
    is_outgoing: true,
    total_net: '100.00',
    total_vat: '24.00',
    total_gross: '124.00',
    mydata_mark: null,
    mydata_uid: '',
    mydata_sent: false,
    mydata_sent_at: null,
    mydata_cancelled: false,
    mydata_cancellation_mark: null,
    correlated_mark: null,
    notes: '',
    items: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('MyDataInvoices', () => {
  it('δείχνει τα τιμολόγια με στοιχεία και κατάσταση «Εκκρεμεί»', async () => {
    mockGetAll.mockResolvedValue([makeInvoice()]);
    render(<MyDataInvoices />);

    expect(await screen.findByText('Α/101')).toBeInTheDocument();
    expect(screen.getByText('ΠΕΛΑΤΗΣ ΑΕ')).toBeInTheDocument();
    expect(screen.getByText('ΑΦΜ 123456783')).toBeInTheDocument();
    expect(screen.getByText('Εκκρεμεί')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Αποστολή/ })).toBeInTheDocument();
    // Default φίλτρο: μόνο εξερχόμενα προς αποστολή
    expect(mockGetAll).toHaveBeenCalledWith({
      direction: 'outgoing',
      mydata_sent: false,
    });
  });

  it('δείχνει κενή κατάσταση όταν δεν υπάρχουν τιμολόγια', async () => {
    mockGetAll.mockResolvedValue([]);
    render(<MyDataInvoices />);
    expect(
      await screen.findByText(/Δεν βρέθηκαν τιμολόγια/)
    ).toBeInTheDocument();
  });

  it('απεσταλμένο: badge «Εστάλη» και κουμπί «Ακύρωση»', async () => {
    mockGetAll.mockResolvedValue([
      makeInvoice({ mydata_sent: true, mydata_mark: 400001234567890 }),
    ]);
    render(<MyDataInvoices />);

    expect(await screen.findByText('Εστάλη')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ακύρωση/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Αποστολή/ })).toBeNull();
  });

  it('ακυρωμένο: badge «Ακυρωμένο» χωρίς κουμπιά ενεργειών', async () => {
    mockGetAll.mockResolvedValue([
      makeInvoice({
        mydata_sent: true,
        mydata_mark: 400001234567890,
        mydata_cancelled: true,
        mydata_cancellation_mark: 400009999999999,
      }),
    ]);
    render(<MyDataInvoices />);

    expect(await screen.findByText('Ακυρωμένο')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Αποστολή/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Ακύρωση/ })).toBeNull();
  });

  it('αποστολή: confirm → API call → μήνυμα επιτυχίας με MARK', async () => {
    mockGetAll.mockResolvedValue([makeInvoice()]);
    mockSend.mockResolvedValue({
      success: true,
      mark: 400001234567890,
      uid: 'UID-1',
      invoice: makeInvoice({ mydata_sent: true, mydata_mark: 400001234567890 }),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<MyDataInvoices />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Αποστολή/ }));

    await waitFor(() => expect(mockSend).toHaveBeenCalledWith(1));
    expect(await screen.findByText(/MARK 400001234567890/)).toBeInTheDocument();
  });

  it('χωρίς confirm δεν στέλνει τίποτα', async () => {
    mockGetAll.mockResolvedValue([makeInvoice()]);
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<MyDataInvoices />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Αποστολή/ }));

    expect(mockSend).not.toHaveBeenCalled();
  });

  it('σφάλμα από ΑΑΔΕ εμφανίζεται στον χρήστη', async () => {
    mockGetAll.mockResolvedValue([makeInvoice()]);
    mockSend.mockRejectedValue({
      response: { data: { error: 'Το myDATA απέρριψε το παραστατικό: [101] Λάθος ΑΦΜ' } },
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<MyDataInvoices />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Αποστολή/ }));

    expect(
      await screen.findByText(/Λάθος ΑΦΜ/)
    ).toBeInTheDocument();
  });

  it('αλλαγή φίλτρου ξαναφορτώνει με σωστές παραμέτρους', async () => {
    mockGetAll.mockResolvedValue([]);
    render(<MyDataInvoices />);
    await screen.findByText(/Δεν βρέθηκαν τιμολόγια/);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Απεσταλμένα' }));
    await waitFor(() =>
      expect(mockGetAll).toHaveBeenLastCalledWith({
        direction: 'outgoing',
        mydata_sent: true,
      })
    );

    await user.click(screen.getByRole('button', { name: 'Όλα' }));
    await waitFor(() =>
      expect(mockGetAll).toHaveBeenLastCalledWith({ direction: 'outgoing' })
    );
  });
});
