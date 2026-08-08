import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import type {
  ClientFull,
  ClientDocument,
  Obligation,
  EmailLog,
  VoIPCall,
  VoIPTicket,
  ClientObligationProfile,
} from '../types';

// ============================================
// QUERY KEYS
// ============================================
const CLIENT_DETAILS_KEY = 'client-details';
const CLIENT_DOCUMENTS_KEY = 'client-documents';
const CLIENT_OBLIGATIONS_KEY = 'client-obligations';
const CLIENT_EMAILS_KEY = 'client-emails';
const CLIENT_CALLS_KEY = 'client-calls';
const CLIENT_TICKETS_KEY = 'client-tickets';
const CLIENT_OBLIGATION_PROFILE_KEY = 'client-obligation-profile';
const CLIENT_MYDATA_CREDENTIALS_KEY = 'client-mydata-credentials';

// ============================================
// API RESPONSE TYPES
// ============================================
interface ClientDocumentsResponse {
  client_id: number;
  client_name: string;
  total_count: number;
  documents: ClientDocument[];
}

interface ClientObligationsResponse {
  client_id: number;
  client_name: string;
  total_count: number;
  obligations: Obligation[];
}

interface ClientEmailsResponse {
  client_id: number;
  client_name: string;
  total_count: number;
  page: number;
  page_size: number;
  emails: EmailLog[];
}

interface ClientCallsResponse {
  client_id: number;
  client_name: string;
  total_count: number;
  page: number;
  page_size: number;
  calls: VoIPCall[];
}

interface ClientTicketsResponse {
  client_id: number;
  client_name: string;
  total_count: number;
  tickets: VoIPTicket[];
}

// ============================================
// HOOKS
// ============================================

/**
 * Get full client details with counts
 */
export function useClientFull(id: number) {
  return useQuery({
    queryKey: [CLIENT_DETAILS_KEY, id],
    queryFn: async () => {
      const response = await apiClient.get<ClientFull>(`/api/v1/clients/${id}/full/`);
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Get client documents
 */
export interface ClientDocumentFilters {
  category?: string;
  year?: number;
  month?: number;
  search?: string;
  current_only?: boolean;
}

export function useClientDocuments(id: number, filters?: ClientDocumentFilters) {
  return useQuery({
    queryKey: [CLIENT_DOCUMENTS_KEY, id, filters],
    queryFn: async () => {
      const params: Record<string, string | number> = {};
      if (filters?.category) params.category = filters.category;
      if (filters?.year) params.year = filters.year;
      if (filters?.month) params.month = filters.month;
      if (filters?.search) params.search = filters.search;
      if (filters?.current_only) params.current_only = '1';
      const response = await apiClient.get<ClientDocumentsResponse>(
        `/api/v1/clients/${id}/documents/`,
        { params }
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Get client obligations
 */
export function useClientObligations(
  id: number,
  filters?: { status?: string; year?: number; month?: number }
) {
  return useQuery({
    queryKey: [CLIENT_OBLIGATIONS_KEY, id, filters],
    queryFn: async () => {
      const response = await apiClient.get<ClientObligationsResponse>(
        `/api/v1/clients/${id}/obligations/`,
        { params: filters }
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Get client email history
 */
export function useClientEmails(id: number, page: number = 1, pageSize: number = 20) {
  return useQuery({
    queryKey: [CLIENT_EMAILS_KEY, id, page, pageSize],
    queryFn: async () => {
      const response = await apiClient.get<ClientEmailsResponse>(
        `/api/v1/clients/${id}/emails/`,
        { params: { page, page_size: pageSize } }
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Get client call history
 */
export function useClientCalls(id: number, page: number = 1, pageSize: number = 20) {
  return useQuery({
    queryKey: [CLIENT_CALLS_KEY, id, page, pageSize],
    queryFn: async () => {
      const response = await apiClient.get<ClientCallsResponse>(
        `/api/v1/clients/${id}/calls/`,
        { params: { page, page_size: pageSize } }
      );
      return response.data;
    },
    enabled: !!id,
  });
}

/**
 * Get client tickets
 */
export function useClientTickets(id: number, status?: string) {
  return useQuery({
    queryKey: [CLIENT_TICKETS_KEY, id, status],
    queryFn: async () => {
      const params = status ? { status } : {};
      const response = await apiClient.get<ClientTicketsResponse>(
        `/api/v1/clients/${id}/tickets/`,
        { params }
      );
      return response.data;
    },
    enabled: !!id,
  });
}

// ============================================
// MUTATIONS
// ============================================

/**
 * Upload document for client
 */
export function useUploadDocument(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      category,
      description,
      obligationId,
      year,
      month,
    }: {
      file: File;
      category?: string;
      description?: string;
      obligationId?: number;
      year?: number;
      month?: number;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (category) formData.append('category', category);
      if (description) formData.append('description', description);
      if (obligationId) formData.append('obligation_id', String(obligationId));
      if (year) formData.append('year', String(year));
      if (month) formData.append('month', String(month));

      const response = await apiClient.post(
        `/api/v1/clients/${clientId}/documents/upload/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_DOCUMENTS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
    },
  });
}

/**
 * Delete document
 */
export function useDeleteDocument(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: number) => {
      const response = await apiClient.delete(
        `/api/v1/clients/${clientId}/documents/${documentId}/delete/`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_DOCUMENTS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
    },
  });
}

/**
 * Create ticket for client
 */
export function useCreateTicket(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      title,
      description,
      priority,
    }: {
      title: string;
      description?: string;
      priority?: 'low' | 'medium' | 'high' | 'urgent';
    }) => {
      const response = await apiClient.post(`api/v1/clients/${clientId}/tickets/`, {
        title,
        description,
        priority,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_TICKETS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
    },
  });
}

/**
 * Update ticket
 */
export function useUpdateTicket(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      ticketId,
      data,
    }: {
      ticketId: number;
      data: {
        title?: string;
        description?: string;
        status?: 'open' | 'in_progress' | 'resolved' | 'closed';
        priority?: 'low' | 'medium' | 'high' | 'urgent';
        assigned_to?: number | null;
      };
    }) => {
      const response = await apiClient.patch(`api/v1/tickets/${ticketId}/`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_TICKETS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
    },
  });
}

/**
 * Delete ticket
 */
export function useDeleteTicket(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ticketId: number) => {
      const response = await apiClient.delete(`api/v1/tickets/${ticketId}/`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_TICKETS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
    },
  });
}

/**
 * Update client data
 */
export function useUpdateClientFull(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Partial<ClientFull>) => {
      const response = await apiClient.patch(`api/v1/clients/${clientId}/`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_DETAILS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
  });
}

// ============================================
// CLIENT OBLIGATION PROFILE HOOKS
// ============================================

/**
 * Get client's obligation profile
 */
export function useClientObligationProfile(clientId: number) {
  return useQuery({
    queryKey: [CLIENT_OBLIGATION_PROFILE_KEY, clientId],
    queryFn: async () => {
      // Note: apiClient baseURL already includes /accounting, so don't prefix it again
      const response = await apiClient.get<ClientObligationProfile>(
        `/api/v1/clients/${clientId}/obligation-profile/`
      );
      return response.data;
    },
    enabled: !!clientId,
  });
}

/**
 * Update client's obligation profile
 */
export function useUpdateClientObligationProfile(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      obligation_type_ids: number[];
      obligation_profile_ids: number[];
    }) => {
      // Note: apiClient baseURL already includes /accounting, so don't prefix it again
      const response = await apiClient.put(
        `/api/v1/clients/${clientId}/obligation-profile/`,
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [CLIENT_OBLIGATION_PROFILE_KEY, clientId],
      });
    },
  });
}

// ============================================
// BULK ASSIGN OBLIGATIONS
// ============================================

interface BulkAssignRequest {
  client_ids: number[];
  obligation_type_ids?: number[];
  obligation_profile_ids?: number[];
  mode?: 'add' | 'replace';
}

interface BulkAssignResponse {
  success: boolean;
  created_count: number;
  updated_count: number;
  clients_processed: number;
  message: string;
}

/**
 * Bulk assign obligation types/profiles to multiple clients
 */
export function useBulkAssignObligations() {
  const queryClient = useQueryClient();

  return useMutation<BulkAssignResponse, Error, BulkAssignRequest>({
    mutationFn: async (data) => {
      const response = await apiClient.post<BulkAssignResponse>(
        '/api/v1/obligations/bulk-assign/',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all client obligation profiles
      queryClient.invalidateQueries({ queryKey: [CLIENT_OBLIGATION_PROFILE_KEY] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
  });
}

// ============================================
// MYDATA CREDENTIALS HOOKS
// ============================================

export interface MyDataCredentialsData {
  id?: number;
  client: number;
  client_name?: string;
  client_afm?: string;
  user_id: string;
  subscription_key: string;
  is_sandbox: boolean;
  is_active: boolean;
  is_verified: boolean;
  has_credentials?: boolean;
  credentials_corrupted?: boolean;
  needs_reconfiguration?: boolean;
  verification_error?: string;
  last_sync_at: string | null;
  last_vat_sync_at: string | null;
  created_at?: string;
  updated_at?: string;
}

/**
 * Get myDATA credentials for a client
 */
export function useClientMyDataCredentials(clientId: number) {
  return useQuery({
    queryKey: [CLIENT_MYDATA_CREDENTIALS_KEY, clientId],
    queryFn: async () => {
      try {
        const response = await apiClient.get<MyDataCredentialsData>(
          `api/mydata/credentials/by-client/${clientId}/`
        );
        return response.data;
      } catch (error: unknown) {
        // Return null if credentials don't exist (404)
        if (error && typeof error === 'object' && 'response' in error) {
          const axiosError = error as { response?: { status?: number } };
          if (axiosError.response?.status === 404) {
            return null;
          }
        }
        throw error;
      }
    },
    enabled: !!clientId,
  });
}

/**
 * Create or update myDATA credentials
 */
export function useSaveMyDataCredentials(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      user_id: string;
      subscription_key: string;
      is_sandbox: boolean;
      is_active?: boolean;
    }) => {
      // Try to get existing credentials first
      try {
        const existing = await apiClient.get(`api/mydata/credentials/by-client/${clientId}/`);
        // Update existing
        const response = await apiClient.patch(
          `api/mydata/credentials/${existing.data.id}/`,
          { ...data, client: clientId }
        );
        return response.data;
      } catch {
        // Create new
        const response = await apiClient.post('api/mydata/credentials/', {
          ...data,
          client: clientId,
          is_active: data.is_active ?? true,
        });
        return response.data;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_MYDATA_CREDENTIALS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: ['mydata', 'clients'] });
    },
  });
}

/**
 * Verify myDATA credentials
 */
export function useVerifyMyDataCredentials(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (credentialsId: number) => {
      const response = await apiClient.post<{ success: boolean; is_verified: boolean; error?: string }>(
        `api/mydata/credentials/${credentialsId}/verify/`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_MYDATA_CREDENTIALS_KEY, clientId] });
    },
  });
}

/**
 * Sync myDATA VAT data
 */
export function useSyncMyDataVAT(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ credentialsId, days = 30 }: { credentialsId: number; days?: number }) => {
      const response = await apiClient.post(`api/mydata/credentials/${credentialsId}/sync/`, {
        days,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_MYDATA_CREDENTIALS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: ['mydata'] });
    },
  });
}

/**
 * Clear corrupted myDATA credentials
 * Use when SECRET_KEY has changed and credentials cannot be decrypted
 */
export function useClearCorruptedCredentials(clientId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (credentialsId: number) => {
      const response = await apiClient.post<{ success: boolean; message: string; needs_reconfiguration: boolean }>(
        `api/mydata/credentials/${credentialsId}/clear_corrupted/`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CLIENT_MYDATA_CREDENTIALS_KEY, clientId] });
      queryClient.invalidateQueries({ queryKey: ['mydata', 'clients'] });
    },
  });
}
