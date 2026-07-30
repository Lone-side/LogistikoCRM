import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PortalUploadSection } from './SharedLinkPortal';
import type { PublicSharedContent } from '../types/fileManager';

const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn() }));

vi.mock('../api/client', () => ({
  default: { post: mockPost, get: vi.fn() },
  apiClient: { post: mockPost, get: vi.fn() },
}));

function makeContent(overrides: Partial<PublicSharedContent> = {}): PublicSharedContent {
  return {
    type: 'folder',
    name: 'Portal test',
    access_level: 'view',
    access_token: 'tok123',
    allow_upload: true,
    upload_note: '',
    document_request: {
      id: 1,
      title: 'Δικαιολογητικά Ιουλίου',
      notes: '',
      due_date: null,
      items: [
        { id: 11, label: 'Τιμολόγια αγορών', category: 'vat', is_received: false },
        { id: 12, label: 'Extrait τράπεζας', category: '', is_received: true },
      ],
    },
    ...overrides,
  } as PublicSharedContent;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('PortalUploadSection — αιτήματα εγγράφων', () => {
  it('δείχνει το checklist με received/pending items', () => {
    render(<PortalUploadSection token="t1" content={makeContent()} email="" />);

    expect(screen.getByText(/Δικαιολογητικά Ιουλίου/)).toBeInTheDocument();
    // Το pending item εμφανίζεται και στο checklist ΚΑΙ στο select option
    expect(screen.getAllByText('Τιμολόγια αγορών').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Extrait τράπεζας')).toBeInTheDocument();
    expect(screen.getByText('Ελήφθη')).toBeInTheDocument();
    // Select με το pending item προεπιλεγμένο
    const select = screen.getByRole('combobox');
    expect(select).toHaveValue('11');
  });

  it('χωρίς document_request δεν εμφανίζεται checklist (regression)', () => {
    render(
      <PortalUploadSection
        token="t1"
        content={makeContent({ document_request: null })}
        email=""
      />
    );
    expect(screen.queryByText(/Ζητούμενα έγγραφα/)).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('το upload στέλνει request_item_id για το επιλεγμένο item', async () => {
    mockPost.mockResolvedValue({
      data: { success: true, uploaded: [{ filename: 'x.pdf' }], errors: [], message: 'ok' },
    });
    const onUploaded = vi.fn();
    render(
      <PortalUploadSection
        token="t1"
        content={makeContent()}
        email=""
        onUploaded={onUploaded}
      />
    );

    const user = userEvent.setup();
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(['%PDF'], 'test.pdf', { type: 'application/pdf' }));
    await user.click(screen.getByRole('button', { name: /Αποστολή/ }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    const formData = mockPost.mock.calls[0][1] as FormData;
    expect(formData.get('request_item_id')).toBe('11');
    expect(formData.get('auth')).toBe('tok123');
    expect(onUploaded).toHaveBeenCalled();
  });

  it('«Άλλο / χωρίς αντιστοίχιση» δεν στέλνει request_item_id', async () => {
    mockPost.mockResolvedValue({
      data: { success: true, uploaded: [{ filename: 'x.pdf' }], errors: [], message: 'ok' },
    });
    render(<PortalUploadSection token="t1" content={makeContent()} email="" />);

    const user = userEvent.setup();
    await user.selectOptions(screen.getByRole('combobox'), '');
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(['%PDF'], 'test.pdf', { type: 'application/pdf' }));
    await user.click(screen.getByRole('button', { name: /Αποστολή/ }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    const formData = mockPost.mock.calls[0][1] as FormData;
    expect(formData.get('request_item_id')).toBeNull();
  });
});
