import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FilePreviewModal } from './FilePreviewModal';

describe('FilePreviewModal', () => {
  it('resets loading state when the preview URL changes', () => {
    const props = {
      isOpen: true,
      onClose: vi.fn(),
      fileName: 'report.pdf',
      fileType: 'pdf',
    };
    const { container, rerender } = render(
      <FilePreviewModal {...props} fileUrl="/first.pdf" />
    );

    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    fireEvent.load(screen.getByTitle('report.pdf'));
    expect(container.querySelector('.animate-spin')).not.toBeInTheDocument();

    rerender(<FilePreviewModal {...props} fileUrl="/second.pdf" />);
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });
});
