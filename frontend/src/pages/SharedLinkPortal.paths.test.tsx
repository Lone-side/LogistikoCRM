/**
 * Οι διευθύνσεις που καλεί το Portal.
 *
 * ΤΟ ΣΦΑΛΜΑ ΠΟΥ ΚΛΕΙΔΩΝΕΙ ΕΔΩ: το `apiClient` έχει ήδη `baseURL`
 * «/accounting» (production) ή «http://localhost:8000/accounting» (dev).
 * Το Portal όμως ζητούσε `/accounting/share/<token>/`, οπότε ο axios
 * ένωνε τα δύο και έστελνε "/accounting/accounting/share/<token>/"
 * → 404 σε ΚΑΘΕ σύνδεσμο πελάτη. Το backend route είναι
 * `accounting/share/<token>/` (accounting/urls.py) — δηλαδή το σωστό
 * μονοπάτι προς τον apiClient είναι ΧΩΡΙΣ το πρόθεμα.
 *
 * Ο κανόνας έχει δύο όψεις και το test τις φυλάει και τις δύο:
 *   - ό,τι φεύγει από τον apiClient  -> ΧΩΡΙΣ «/accounting» (το βάζει το baseURL)
 *   - ό,τι πάει στο window.open      -> ΜΕ «/accounting» (ωμό URL του browser)
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SharedLinkPortal, { PortalUploadSection } from './SharedLinkPortal';
import type { PublicSharedContent } from '../types/fileManager';

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('../api/client', () => ({
  default: { get: mockGet, post: mockPost },
  apiClient: { get: mockGet, post: mockPost },
}));

const TOKEN = 'tok123';

function renderPortal() {
  return render(
    <MemoryRouter initialEntries={[`/share/${TOKEN}`]}>
      <Routes>
        <Route path="/share/:token" element={<SharedLinkPortal />} />
      </Routes>
    </MemoryRouter>
  );
}

const OPEN_CONTENT = {
  data: {
    type: 'folder',
    name: 'Φάκελος Ιουλίου',
    access_level: 'download',
    access_token: 'granted-token',
    allow_upload: false,
    documents: [
      {
        id: 7,
        filename: 'a.pdf',
        file_type: 'pdf',
        category: 'ΦΠΑ',
        file_size_display: '10 KB',
        uploaded_at: '2026-08-01T10:00:00Z',
      },
    ],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SharedLinkPortal — μονοπάτια API', () => {
  it('το GET περιεχομένου δεν διπλασιάζει το «/accounting»', async () => {
    mockGet.mockResolvedValue(OPEN_CONTENT);
    renderPortal();

    await waitFor(() => expect(mockGet).toHaveBeenCalled());

    const path = mockGet.mock.calls[0][0] as string;
    expect(path).toBe(`/share/${TOKEN}/`);
    expect(path.startsWith('/accounting')).toBe(false);
  });

  it('το POST αυθεντικοποίησης δεν διπλασιάζει το «/accounting»', async () => {
    mockGet.mockResolvedValue({
      data: { requires_auth: true, needs_password: true, needs_email: false, name: 'Φ' },
    });
    mockPost.mockResolvedValue(OPEN_CONTENT);
    renderPortal();

    const field = await screen.findByLabelText(/κωδικ/i);
    await userEvent.type(field, 'mistiko');
    await userEvent.click(screen.getByRole('button', { name: /πρόσβαση|είσοδος|υποβολή/i }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost.mock.calls[0][0]).toBe(`/share/${TOKEN}/`);
  });

  it('το upload δεν διπλασιάζει το «/accounting»', async () => {
    mockPost.mockResolvedValue({ data: { uploaded: [], errors: [] } });
    const content = {
      type: 'folder',
      name: 'Φ',
      access_level: 'download',
      access_token: 'tok',
      allow_upload: true,
      upload_note: '',
    } as PublicSharedContent;

    render(<PortalUploadSection token={TOKEN} content={content} email="" />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(['x'], 'a.pdf', { type: 'application/pdf' }));
    await userEvent.click(screen.getByRole('button', { name: /μεταφόρτωση|ανέβασμα|αποστολή/i }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost.mock.calls[0][0]).toBe(`/share/${TOKEN}/upload/`);
  });

  it('η λήψη ανοίγει ΩΜΟ url του browser — αυτό ΠΡΕΠΕΙ να έχει «/accounting»', async () => {
    mockGet.mockResolvedValue(OPEN_CONTENT);
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    renderPortal();

    await screen.findByText(/Φάκελος Ιουλίου/);
    const [downloadBtn] = await screen.findAllByRole('button', { name: /λήψη/i });
    await userEvent.click(downloadBtn);

    expect(openSpy).toHaveBeenCalled();
    const url = openSpy.mock.calls[0][0] as string;
    expect(url.startsWith(`/accounting/share/${TOKEN}/download/`)).toBe(true);
    openSpy.mockRestore();
  });
});
