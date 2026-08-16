/**
 * Η πύλη αυθεντικοποίησης του portal πελατών.
 *
 * Είναι το ΜΟΝΟ πράγμα που χωρίζει τα έγγραφα ενός πελάτη από οποιονδήποτε
 * έχει το link. Το SharedLinkPortal.test.tsx καλύπτει το upload· εδώ
 * καλύπτεται το όριο πρόσβασης.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SharedLinkPortal from './SharedLinkPortal';

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('../api/client', () => ({
  default: { get: mockGet, post: mockPost },
  apiClient: { get: mockGet, post: mockPost },
}));

function renderPortal(token = 'tok123') {
  return render(
    <MemoryRouter initialEntries={[`/share/${token}`]}>
      <Routes>
        <Route path="/share/:token" element={<SharedLinkPortal />} />
      </Routes>
    </MemoryRouter>
  );
}

/** Απάντηση «χρειάζεται αυθεντικοποίηση» του GET. */
function gated(overrides = {}) {
  return {
    data: {
      requires_auth: true,
      needs_password: true,
      needs_email: false,
      name: 'Φάκελος Ιουλίου',
      access_level: 'view',
      ...overrides,
    },
  };
}

/** Το πραγματικό περιεχόμενο, μετά από επιτυχή αυθεντικοποίηση. */
const CONTENT = {
  data: {
    type: 'folder',
    name: 'Φάκελος Ιουλίου',
    access_level: 'view',
    access_token: 'granted-token',
    allow_upload: false,
    files: [],
  },
};

describe('SharedLinkPortal — πύλη πρόσβασης', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('δεν αποκαλύπτει περιεχόμενο όσο απαιτείται κωδικός', async () => {
    mockGet.mockResolvedValue(gated());
    renderPortal();

    expect(await screen.findByLabelText('Κωδικός πρόσβασης')).toBeInTheDocument();
    // Το όνομα του φακέλου φαίνεται (το επιστρέφει το backend), αλλά ΟΧΙ αρχεία.
    expect(screen.queryByText(/Λήψη/)).not.toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('κενός κωδικός δεν φεύγει καν στο δίκτυο', async () => {
    mockGet.mockResolvedValue(gated());
    renderPortal();
    await screen.findByLabelText('Κωδικός πρόσβασης');

    await userEvent.click(screen.getByRole('button', { name: /Πρόσβαση|Είσοδος|Συνέχεια/ }));

    expect(await screen.findByText('Εισάγετε τον κωδικό')).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('λάθος κωδικός: δείχνει το σφάλμα και ΜΕΝΕΙ κλειδωμένο', async () => {
    mockGet.mockResolvedValue(gated());
    mockPost.mockRejectedValue({
      isAxiosError: true,
      response: { status: 403, data: { error: 'Λάθος κωδικός' } },
    });
    renderPortal();

    await userEvent.type(
      await screen.findByLabelText('Κωδικός πρόσβασης'),
      'λάθος'
    );
    await userEvent.click(
      screen.getByRole('button', { name: /Πρόσβαση|Είσοδος|Συνέχεια/ })
    );

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    // Η φόρμα παραμένει — δεν ξεκλείδωσε τίποτα.
    expect(screen.getByLabelText('Κωδικός πρόσβασης')).toBeInTheDocument();
  });

  it('σωστός κωδικός: εμφανίζεται το περιεχόμενο και φεύγει η φόρμα', async () => {
    mockGet.mockResolvedValue(gated());
    mockPost.mockResolvedValue(CONTENT);
    renderPortal();

    await userEvent.type(
      await screen.findByLabelText('Κωδικός πρόσβασης'),
      'σωστός'
    );
    await userEvent.click(
      screen.getByRole('button', { name: /Πρόσβαση|Είσοδος|Συνέχεια/ })
    );

    await waitFor(() =>
      expect(screen.queryByLabelText('Κωδικός πρόσβασης')).not.toBeInTheDocument()
    );
    expect(mockPost).toHaveBeenCalledWith(
      '/accounting/share/tok123/',
      expect.objectContaining({ password: 'σωστός' })
    );
  });

  it('όταν ζητείται email, ΔΕΝ στέλνεται πεδίο κωδικού', async () => {
    mockGet.mockResolvedValue(gated({ needs_password: false, needs_email: true }));
    mockPost.mockResolvedValue(CONTENT);
    renderPortal();

    await userEvent.type(await screen.findByLabelText('Email'), 'pelatis@example.gr');
    await userEvent.click(
      screen.getByRole('button', { name: /Πρόσβαση|Είσοδος|Συνέχεια/ })
    );

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost).toHaveBeenCalledWith(
      '/accounting/share/tok123/',
      expect.objectContaining({ email: 'pelatis@example.gr', password: undefined })
    );
  });

  it('ληγμένος σύνδεσμος (410): μήνυμα του server, καμία φόρμα', async () => {
    mockGet.mockRejectedValue({
      response: { status: 410, data: { error: 'Ο σύνδεσμος έληξε' } },
    });
    renderPortal();

    expect(await screen.findByText('Ο σύνδεσμος έληξε')).toBeInTheDocument();
    expect(screen.queryByLabelText('Κωδικός πρόσβασης')).not.toBeInTheDocument();
  });

  it('γενικό σφάλμα δεν διαρρέει λεπτομέρειες', async () => {
    mockGet.mockRejectedValue({ response: { status: 500, data: { error: 'psql: FATAL' } } });
    renderPortal();

    expect(await screen.findByText('Σφάλμα κατά τη φόρτωση')).toBeInTheDocument();
    expect(screen.queryByText(/FATAL/)).not.toBeInTheDocument();
  });
});
