/**
 * useFileManager.ts
 * Comprehensive hooks for File Manager API
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import type {
  FileManagerDocument,
  DocumentTag,
  SharedLink,
  CreateSharedLinkRequest,
  DocumentFavorite,
  DocumentCollection,
  FileManagerStats,
  DocumentFilters,
  DocumentPreview,
  VersionHistory,
  BrowseResponse,
  UploadResponse,
  AccessLogEntry,
} from '../types/fileManager';
import type { PaginatedResponse } from '../types';

const FILE_MANAGER_KEY = 'file-manager';

// ============================================
// DOCUMENTS
// ============================================

/**
 * Fetch documents with filters
 */
export function useFileManagerDocuments(filters?: DocumentFilters) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'documents', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<FileManagerDocument>>(
        'api/v1/file-manager/documents/',
        { params: filters }
      );
      return response.data;
    },
  });
}

/**
 * Fetch single document
 */
export function useFileManagerDocument(id: number) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'documents', id],
    queryFn: async () => {
      const response = await apiClient.get<FileManagerDocument>(
        `api/v1/file-manager/documents/${id}/`
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Upload documents
 */
export function useUploadDocuments() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      files: File[];
      client_id: number;
      obligation_id?: number;
      document_category?: string;
      description?: string;
      year?: number;
      month?: number;
    }): Promise<UploadResponse> => {
      const formData = new FormData();

      // Append files
      data.files.forEach((file) => {
        formData.append('files', file);
      });

      formData.append('client_id', String(data.client_id));
      if (data.obligation_id) formData.append('obligation_id', String(data.obligation_id));
      if (data.document_category) formData.append('document_category', data.document_category);
      if (data.description) formData.append('description', data.description);
      if (data.year) formData.append('year', String(data.year));
      if (data.month) formData.append('month', String(data.month));

      const response = await apiClient.post<UploadResponse>(
        'api/v1/file-manager/documents/upload/',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

/**
 * Delete document
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      await apiClient.delete(`api/v1/file-manager/documents/${documentId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

/**
 * Bulk delete documents
 */
export function useBulkDeleteDocuments() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentIds: number[]) => {
      const response = await apiClient.post('api/v1/file-manager/documents/bulk-delete/', {
        document_ids: documentIds,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

/**
 * Get document preview info
 */
export function useDocumentPreview(documentId: number) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'preview', documentId],
    queryFn: async () => {
      const response = await apiClient.get<DocumentPreview>(
        `api/v1/file-manager/documents/${documentId}/preview/`
      );
      return response.data;
    },
    enabled: !!documentId,
  });
}

/**
 * Get document version history
 */
export function useDocumentVersions(documentId: number) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'versions', documentId],
    queryFn: async () => {
      const response = await apiClient.get<VersionHistory>(
        `api/v1/file-manager/documents/${documentId}/versions/`
      );
      return response.data;
    },
    enabled: !!documentId,
  });
}

/**
 * Add tags to document
 */
export function useAddTagsToDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ documentId, tagIds }: { documentId: number; tagIds: number[] }) => {
      const response = await apiClient.post(
        `api/v1/file-manager/documents/${documentId}/tags/`,
        { tag_ids: tagIds }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

/**
 * Remove tag from document
 */
export function useRemoveTagFromDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ documentId, tagId }: { documentId: number; tagId: number }) => {
      await apiClient.delete(`api/v1/file-manager/documents/${documentId}/tags/${tagId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

// ============================================
// TAGS
// ============================================

/**
 * Fetch all tags
 */
export function useTags() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'tags'],
    queryFn: async () => {
      const response = await apiClient.get<DocumentTag[]>('api/v1/file-manager/tags/');
      return response.data;
    },
  });
}

/**
 * Create tag
 */
export function useCreateTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Partial<DocumentTag>) => {
      const response = await apiClient.post<DocumentTag>('api/v1/file-manager/tags/', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'tags'] });
    },
  });
}

/**
 * Update tag
 */
export function useUpdateTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<DocumentTag> }) => {
      const response = await apiClient.patch<DocumentTag>(
        `api/v1/file-manager/tags/${id}/`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'tags'] });
    },
  });
}

/**
 * Delete tag
 */
export function useDeleteTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (tagId: number) => {
      await apiClient.delete(`api/v1/file-manager/tags/${tagId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'tags'] });
    },
  });
}

// ============================================
// SHARED LINKS
// ============================================

/**
 * Fetch shared links
 */
export function useSharedLinks() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'shared-links'],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<SharedLink>>(
        'api/v1/file-manager/shared-links/'
      );
      return response.data;
    },
  });
}

/**
 * Create shared link
 */
export function useCreateSharedLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateSharedLinkRequest) => {
      const response = await apiClient.post<SharedLink>(
        'api/v1/file-manager/shared-links/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'shared-links'] });
    },
  });
}

/**
 * Update shared link
 */
export function useUpdateSharedLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<SharedLink> }) => {
      const response = await apiClient.patch<SharedLink>(
        `api/v1/file-manager/shared-links/${id}/`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'shared-links'] });
    },
  });
}

/**
 * Delete shared link
 */
export function useDeleteSharedLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (linkId: number) => {
      await apiClient.delete(`api/v1/file-manager/shared-links/${linkId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'shared-links'] });
    },
  });
}

/**
 * Regenerate shared link token
 */
export function useRegenerateToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (linkId: number) => {
      const response = await apiClient.post<SharedLink>(
        `api/v1/file-manager/shared-links/${linkId}/regenerate-token/`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'shared-links'] });
    },
  });
}

/**
 * Get access logs for shared link
 */
export function useSharedLinkAccessLogs(linkId: number) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'shared-links', linkId, 'logs'],
    queryFn: async () => {
      const response = await apiClient.get<{
        shared_link_id: number;
        total_views: number;
        total_downloads: number;
        logs: AccessLogEntry[];
      }>(`api/v1/file-manager/shared-links/${linkId}/access-logs/`);
      return response.data;
    },
    enabled: !!linkId,
  });
}

// ============================================
// FAVORITES
// ============================================

/**
 * Fetch favorites
 */
export function useFavorites() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'favorites'],
    queryFn: async () => {
      const response = await apiClient.get<DocumentFavorite[]>(
        'api/v1/file-manager/favorites/'
      );
      return response.data;
    },
  });
}

/**
 * Add to favorites
 */
export function useAddFavorite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ documentId, note }: { documentId: number; note?: string }) => {
      const response = await apiClient.post('api/v1/file-manager/favorites/', {
        document_id: documentId,
        note,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

/**
 * Remove from favorites
 */
export function useRemoveFavorite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      await apiClient.delete(`api/v1/file-manager/favorites/${documentId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}

// ============================================
// COLLECTIONS
// ============================================

/**
 * Fetch collections
 */
export function useCollections() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'collections'],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<DocumentCollection>>(
        'api/v1/file-manager/collections/'
      );
      return response.data;
    },
  });
}

/**
 * Fetch single collection
 */
export function useCollection(id: number) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'collections', id],
    queryFn: async () => {
      const response = await apiClient.get<DocumentCollection>(
        `api/v1/file-manager/collections/${id}/`
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Create collection
 */
export function useCreateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Partial<DocumentCollection>) => {
      const response = await apiClient.post<DocumentCollection>(
        'api/v1/file-manager/collections/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'collections'] });
    },
  });
}

/**
 * Update collection
 */
export function useUpdateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<DocumentCollection> }) => {
      const response = await apiClient.patch<DocumentCollection>(
        `api/v1/file-manager/collections/${id}/`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'collections'] });
    },
  });
}

/**
 * Delete collection
 */
export function useDeleteCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (collectionId: number) => {
      await apiClient.delete(`api/v1/file-manager/collections/${collectionId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'collections'] });
    },
  });
}

/**
 * Add documents to collection
 */
export function useAddToCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      collectionId,
      documentIds,
    }: {
      collectionId: number;
      documentIds: number[];
    }) => {
      const response = await apiClient.post(
        `api/v1/file-manager/collections/${collectionId}/documents/`,
        { document_ids: documentIds }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'collections'] });
    },
  });
}

/**
 * Remove document from collection
 */
export function useRemoveFromCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ collectionId, documentId }: { collectionId: number; documentId: number }) => {
      await apiClient.delete(
        `api/v1/file-manager/collections/${collectionId}/documents/${documentId}/`
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'collections'] });
    },
  });
}

// ============================================
// STATS & BROWSE
// ============================================

/**
 * Fetch file manager stats
 */
export function useFileManagerStats() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'stats'],
    queryFn: async () => {
      const response = await apiClient.get<FileManagerStats>(
        'api/v1/file-manager/stats/'
      );
      return response.data;
    },
  });
}

/**
 * Fetch recent documents
 */
export function useRecentDocuments(limit = 20) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'recent', limit],
    queryFn: async () => {
      const response = await apiClient.get<FileManagerDocument[]>(
        'api/v1/file-manager/recent/',
        { params: { limit } }
      );
      return response.data;
    },
  });
}

/**
 * Browse folder structure
 */
export function useBrowseFolders(params?: { client_id?: number; year?: string; month?: string }) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'browse', params],
    queryFn: async () => {
      const response = await apiClient.get<BrowseResponse>(
        'api/v1/file-manager/browse/',
        { params }
      );
      return response.data;
    },
  });
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Download document
 */
export async function downloadDocument(documentId: number, filename: string): Promise<void> {
  const response = await apiClient.get(
    `api/v1/file-manager/documents/${documentId}/download/`,
    { responseType: 'blob' }
  );

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Copy share link to clipboard
 */
export async function copyShareLink(publicUrl: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(window.location.origin + publicUrl);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get file icon based on type
 */
export function getFileIcon(fileType: string): string {
  const type = fileType.toLowerCase();
  const iconMap: Record<string, string> = {
    pdf: 'file-text',
    doc: 'file-text',
    docx: 'file-text',
    xls: 'file-spreadsheet',
    xlsx: 'file-spreadsheet',
    jpg: 'image',
    jpeg: 'image',
    png: 'image',
    gif: 'image',
    webp: 'image',
    zip: 'file-archive',
    rar: 'file-archive',
  };
  return iconMap[type] || 'file';
}

/**
 * Get file color based on type
 */
export function getFileColor(fileType: string): string {
  const type = fileType.toLowerCase();
  const colorMap: Record<string, string> = {
    pdf: '#EF4444',
    doc: '#3B82F6',
    docx: '#3B82F6',
    xls: '#10B981',
    xlsx: '#10B981',
    jpg: '#8B5CF6',
    jpeg: '#8B5CF6',
    png: '#8B5CF6',
    gif: '#8B5CF6',
    webp: '#8B5CF6',
    zip: '#F59E0B',
    rar: '#F59E0B',
  };
  return colorMap[type] || '#6B7280';
}


// ============================================
// FILESYSTEM BROWSER (NEW)
// ============================================

export interface FilesystemFolder {
  name: string;
  path: string;
  item_count: number;
}

export interface FilesystemFile {
  name: string;
  path: string;
  size: number;
  size_display: string;
  modified: string;
  extension: string;
  in_database: boolean;
}

export interface FilesystemBrowseResponse {
  path: string;
  exists: boolean;
  breadcrumb: { name: string; path: string }[];
  folders: FilesystemFolder[];
  files: FilesystemFile[];
  total_folders: number;
  total_files: number;
  message?: string;
}

export interface FolderTemplate {
  id: string;
  name: string;
  description: string;
  folder_count: number;
}

export interface SyncResponse {
  success: boolean;
  synced: number;
  errors: number;
  synced_files: { filename: string; path: string; id: number }[];
  error_files: { filename: string; error: string }[];
  message: string;
}

/**
 * Browse actual filesystem (not just database records)
 */
export function useFilesystemBrowser(params?: { path?: string; client_id?: number }) {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'filesystem', params],
    queryFn: async () => {
      const response = await apiClient.get<FilesystemBrowseResponse>(
        'api/v1/file-manager/filesystem/',
        { params }
      );
      return response.data;
    },
  });
}

/**
 * Create a new folder in filesystem
 */
export function useCreateFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { path: string; folder_name: string }) => {
      const response = await apiClient.post(
        'api/v1/file-manager/filesystem/create-folder/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'filesystem'] });
    },
  });
}

/**
 * Get available folder templates
 */
export function useFolderTemplates() {
  return useQuery({
    queryKey: [FILE_MANAGER_KEY, 'templates'],
    queryFn: async () => {
      const response = await apiClient.get<{ templates: FolderTemplate[] }>(
        'api/v1/file-manager/filesystem/templates/'
      );
      return response.data.templates;
    },
  });
}

/**
 * Apply a folder template to a client
 */
export function useApplyTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { client_id: number; template?: string }) => {
      const response = await apiClient.post(
        'api/v1/file-manager/filesystem/templates/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY, 'filesystem'] });
    },
  });
}

/**
 * Sync filesystem files to database
 */
export function useSyncFilesystem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { client_id: number }) => {
      const response = await apiClient.post<SyncResponse>(
        'api/v1/file-manager/filesystem/sync/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILE_MANAGER_KEY] });
    },
  });
}
