import { useQuery } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import apiClient from '../api/client';
import type { AxiosResponse } from 'axios';

export type ReportPeriod = 'today' | 'week' | 'month' | 'quarter' | 'year' | 'all';
export type ExportType = 'clients' | 'obligations' | 'financial' | 'performance';
export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

interface ObligationByType {
  obligation_type__name: string;
  obligation_type__code: string;
  count: number;
}

interface MonthlyActivity {
  month: string;
  month_num: number;
  year: number;
  count: number;
}

interface Comparison {
  clients_change: number;
  completed_change: number;
}

interface ReportsStats {
  period: ReportPeriod;
  total_clients: number;
  completed_obligations: number;
  pending_obligations: number;
  overdue_obligations: number;
  obligations_by_type: ObligationByType[];
  monthly_activity: MonthlyActivity[];
  completion_rate: number;
  comparison: Comparison;
  generated_at: string;
}

interface ExportInfo {
  name: string;
  type: string;
  description: string;
  formats: string[];
}

interface ReportsExport {
  available_exports: ExportInfo[];
  current_request: {
    type: string;
    format: string;
    period: string;
  };
}

const REPORTS_KEY = 'reports';

export function useReportsStats(period: ReportPeriod = 'month') {
  return useQuery({
    queryKey: [REPORTS_KEY, 'stats', period],
    queryFn: async () => {
      const response = await apiClient.get<ReportsStats>(`/api/reports/stats/?period=${period}`);
      return response.data;
    },
    staleTime: 30000, // 30 seconds
    retry: 1,
  });
}

export function useReportsExport() {
  return useQuery({
    queryKey: [REPORTS_KEY, 'export'],
    queryFn: async () => {
      const response = await apiClient.get<ReportsExport>('/api/reports/export/');
      return response.data;
    },
    staleTime: 60000, // 1 minute
  });
}

// ============================================
// EXPORT DOWNLOAD FUNCTIONS
// ============================================

/**
 * Helper function to trigger file download from blob response
 */
function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Extract filename from Content-Disposition header
 */
function getFilenameFromResponse(response: AxiosResponse<Blob>, defaultFilename: string): string {
  const contentDisposition = response.headers['content-disposition'];
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match) return match[1];
  }
  return defaultFilename;
}

/**
 * Download clients report (Excel)
 */
export async function downloadClientsReport() {
  const response = await apiClient.get('api/v1/export/clients/csv/', {
    responseType: 'blob',
  });
  const filename = getFilenameFromResponse(response, 'Pelates.xlsx');
  downloadBlob(response.data, filename);
}

/**
 * Download obligations report (Excel)
 * @param period - Report period filter
 */
export async function downloadObligationsReport(period: ReportPeriod = 'month') {
  const response = await apiClient.get(`api/reports/export/download/?type=obligations&format=xlsx&period=${period}`, {
    responseType: 'blob',
  });
  const filename = getFilenameFromResponse(response, `Ypoxreoseis_${period}.xlsx`);
  downloadBlob(response.data, filename);
}

/**
 * Download client PDF report
 * @param clientId - Client ID
 */
export async function downloadClientPdf(clientId: number) {
  const response = await apiClient.get(`/accounting/reports/client/${clientId}/pdf/`, {
    responseType: 'blob',
  });
  const filename = getFilenameFromResponse(response, `client_${clientId}.pdf`);
  downloadBlob(response.data, filename);
}

/**
 * Download monthly report PDF
 * @param year - Year
 * @param month - Month (1-12)
 */
export async function downloadMonthlyPdf(year: number, month: number) {
  const response = await apiClient.get(`/accounting/reports/monthly/${year}/${month}/pdf/`, {
    responseType: 'blob',
  });
  const filename = getFilenameFromResponse(response, `report_${year}_${String(month).padStart(2, '0')}.pdf`);
  downloadBlob(response.data, filename);
}

/**
 * Download filtered obligations Excel export
 * @param filters - Filter parameters
 */
export async function downloadFilteredObligationsExcel(filters: {
  status?: string;
  client?: string;
  type?: string;
  date_from?: string;
  date_to?: string;
}) {
  const params = new URLSearchParams();
  if (filters.status) params.append('status', filters.status);
  if (filters.client) params.append('client', filters.client);
  if (filters.type) params.append('type', filters.type);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);

  const response = await apiClient.post(`/accounting/export-excel/?${params.toString()}`, null, {
    responseType: 'blob',
  });
  const filename = getFilenameFromResponse(response, 'Ypoxreoseis.xlsx');
  downloadBlob(response.data, filename);
}

// ============================================
// EXPORT HOOK WITH LOADING STATES
// ============================================

interface ExportState {
  isExporting: boolean;
  exportType: ExportType | null;
  error: Error | null;
}

/**
 * Hook for managing report exports with loading states
 */
export function useReportExport() {
  const [state, setState] = useState<ExportState>({
    isExporting: false,
    exportType: null,
    error: null,
  });

  const exportClients = useCallback(async () => {
    setState({ isExporting: true, exportType: 'clients', error: null });
    try {
      await downloadClientsReport();
      setState({ isExporting: false, exportType: null, error: null });
    } catch (err) {
      setState({ isExporting: false, exportType: null, error: err as Error });
      throw err;
    }
  }, []);

  const exportObligations = useCallback(async (period: ReportPeriod = 'month') => {
    void period;
    setState({ isExporting: true, exportType: 'obligations', error: null });
    try {
      await downloadFilteredObligationsExcel({});
      setState({ isExporting: false, exportType: null, error: null });
    } catch (err) {
      setState({ isExporting: false, exportType: null, error: err as Error });
      throw err;
    }
  }, []);

  const exportMonthlyPdf = useCallback(async (year: number, month: number) => {
    setState({ isExporting: true, exportType: 'performance', error: null });
    try {
      await downloadMonthlyPdf(year, month);
      setState({ isExporting: false, exportType: null, error: null });
    } catch (err) {
      setState({ isExporting: false, exportType: null, error: err as Error });
      throw err;
    }
  }, []);

  const exportClientPdf = useCallback(async (clientId: number) => {
    setState({ isExporting: true, exportType: 'clients', error: null });
    try {
      await downloadClientPdf(clientId);
      setState({ isExporting: false, exportType: null, error: null });
    } catch (err) {
      setState({ isExporting: false, exportType: null, error: err as Error });
      throw err;
    }
  }, []);

  return {
    ...state,
    exportClients,
    exportObligations,
    exportMonthlyPdf,
    exportClientPdf,
  };
}

// ============================================
// VAT SUMMARY
// ============================================

export type VATReportPeriodType = 'month' | 'quarter';

interface VATClient {
  client_id: number;
  client_name: string;
  client_afm: string;
  total_obligations: number;
  completed: number;
  pending: number;
  overdue: number;
  vat_output?: number;
  vat_input?: number;
  vat_balance?: number;
  has_mydata?: boolean;
}

interface VATSummaryResponse {
  period: {
    year: number;
    type: VATReportPeriodType;
    period: number;
    label: string;
    months: number[];
  };
  totals: {
    total_clients: number;
    total_obligations: number;
    completed: number;
    pending: number;
    overdue: number;
    vat_output: number;
    vat_input: number;
    vat_balance: number;
  };
  clients: VATClient[];
  generated_at: string;
}

export function useVATSummary(year: number, periodType: VATReportPeriodType, period: number) {
  return useQuery({
    queryKey: [REPORTS_KEY, 'vat-summary', year, periodType, period],
    queryFn: async () => {
      const response = await apiClient.get<VATSummaryResponse>(
        `/api/reports/vat-summary/?year=${year}&period_type=${periodType}&period=${period}`
      );
      return response.data;
    },
    staleTime: 60000, // 1 minute
    enabled: !!year && !!period,
  });
}

/**
 * Download VAT summary Excel report
 */
export async function downloadVATSummaryExcel(year: number, periodType: VATReportPeriodType, period: number) {
  const response = await apiClient.get(
    `/api/reports/vat-summary/?year=${year}&period_type=${periodType}&period=${period}&format=xlsx`,
    { responseType: 'blob' }
  );
  const filename = getFilenameFromResponse(response, `FPA_${year}_${period}.xlsx`);
  downloadBlob(response.data, filename);
}
