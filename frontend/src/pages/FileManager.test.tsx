import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { docs, noopMutation } = vi.hoisted(() => ({
  docs: { data: { results: [], count: 0 }, isLoading: false, refetch: vi.fn() },
  noopMutation: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('../hooks/useFileManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useFileManager')>()
  return {
    ...actual,
    useFileManagerDocuments: () => docs,
    useFileManagerStats: () => ({ data: undefined }),
    useBrowseFolders: () => ({ data: [] }),
    useTags: () => ({ data: [] }),
    useUploadDocuments: noopMutation,
    useDeleteDocument: noopMutation,
    useBulkDeleteDocuments: noopMutation,
    useAddFavorite: noopMutation,
    useRemoveFavorite: noopMutation,
    useCreateSharedLink: noopMutation,
  }
})
vi.mock('../hooks/useClients', () => ({ useClients: () => ({ data: { results: [] } }) }))
vi.mock('../hooks/useObligations', () => ({ useObligations: () => ({ data: { results: [] } }) }))

import FileManager from './FileManager'

const renderFM = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><FileManager /></QueryClientProvider>,
  )
}

describe('FileManager', () => {
  beforeEach(() => {
    docs.data = { results: [], count: 0 }
    docs.isLoading = false
  })

  it('renders without crashing (empty)', () => {
    const { container } = renderFM()
    expect(container).toBeTruthy()
  })

  it('renders in loading state', () => {
    docs.isLoading = true
    const { container } = renderFM()
    expect(container).toBeTruthy()
  })
})
