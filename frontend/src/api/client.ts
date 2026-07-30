import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

// Σε production build (πίσω από nginx) το API είναι same-origin στο /accounting.
// Σε development ο Vite dev server (5173) μιλά απευθείας στο Django (8000).
const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:8000/accounting' : '/accounting');

// Create axios instance
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add JWT token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('accessToken');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 error and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refreshToken');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh/`, {
            refresh: refreshToken,
          }, {
            headers: { 'Content-Type': 'application/json' }
          });

          const { access } = response.data;
          localStorage.setItem('accessToken', access);

          // Retry the original request with new token
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access}`;
          }
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Auth API functions
export const authApi = {
  login: async (username: string, password: string) => {
    const response = await apiClient.post('api/auth/login/', { username, password });
    return response.data;
  },

  refreshToken: async (refresh: string) => {
    const response = await apiClient.post('api/auth/refresh/', { refresh });
    return response.data;
  },

  verifyToken: async (token: string) => {
    const response = await apiClient.post('api/auth/verify/', { token });
    return response.data;
  },

  getCurrentUser: async () => {
    const response = await apiClient.get('api/auth/me/');
    return response.data;
  },

  updateProfile: async (data: { first_name?: string; last_name?: string; email?: string }) => {
    const response = await apiClient.patch('api/auth/me/', data);
    return response.data;
  },
};

// Clients API functions
export const clientsApi = {
  getAll: async (params?: { search?: string; page?: number; page_size?: number }) => {
    const response = await apiClient.get('api/v1/clients/', { params });
    return response.data;
  },

  getById: async (id: number) => {
    const response = await apiClient.get(`api/v1/clients/${id}/`);
    return response.data;
  },
};

// Obligations API functions
export const obligationsApi = {
  getAll: async (params?: { search?: string; page?: number; page_size?: number; status?: string }) => {
    const response = await apiClient.get('api/v1/obligations/', { params });
    return response.data;
  },

  getById: async (id: number) => {
    const response = await apiClient.get(`api/v1/obligations/${id}/`);
    return response.data;
  },
};

// Global Search API
export interface SearchResultItem {
  id: number;
  title: string;
  subtitle: string;
  url: string;
  type: 'client' | 'obligation' | 'ticket' | 'call';
  extra?: Record<string, unknown>;
}

export interface GlobalSearchResponse {
  query: string;
  results: {
    clients: SearchResultItem[];
    obligations: SearchResultItem[];
    tickets: SearchResultItem[];
    calls: SearchResultItem[];
  };
  total: number;
  error?: string;
}

export const searchApi = {
  globalSearch: async (query: string): Promise<GlobalSearchResponse> => {
    const response = await apiClient.get('api/v1/search/', { params: { q: query } });
    return response.data;
  },
};

// GSIS API (Αναζήτηση στοιχείων με ΑΦΜ)
export interface AFMData {
  afm: string;
  onomasia: string;
  doy: string;
  doy_descr: string;
  legal_form: string;
  legal_form_descr: string;
  postal_address: string;
  postal_address_no: string;
  postal_zip_code: string;
  postal_area: string;
  registration_date: string | null;
  stop_date: string | null;
  deactivation_flag: boolean;
  firm_flag: boolean;
  activities: Array<{
    firm_act_descr?: string;
    firm_act_kind?: string;
    firm_act_kind_descr?: string;
  }>;
}

export interface AFMLookupResponse {
  success: boolean;
  data?: AFMData;
  error?: string;
}

export interface GSISStatusResponse {
  configured: boolean;
  active: boolean;
  afm?: string;
  username?: string;
}

export const gsisApi = {
  // Αναζήτηση στοιχείων με ΑΦΜ
  lookupAfm: async (afm: string): Promise<AFMLookupResponse> => {
    try {
      const response = await apiClient.post('api/v1/afm-lookup/', { afm });
      return response.data;
    } catch (error: unknown) {
      // Extract error message from axios error response
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { error?: string } } };
        if (axiosError.response?.data?.error) {
          return { success: false, error: axiosError.response.data.error };
        }
      }
      return { success: false, error: 'Σφάλμα επικοινωνίας με τον server' };
    }
  },

  // Κατάσταση ρυθμίσεων GSIS
  getStatus: async (): Promise<GSISStatusResponse> => {
    const response = await apiClient.get('api/v1/gsis/status/');
    return response.data;
  },

  // Ενημέρωση ρυθμίσεων GSIS
  updateSettings: async (data: { afm: string; username: string; password?: string; is_active?: boolean }) => {
    const response = await apiClient.post('api/v1/gsis/settings/', data);
    return response.data;
  },

  // Δοκιμή σύνδεσης
  testConnection: async () => {
    const response = await apiClient.post('api/v1/gsis/test/');
    return response.data;
  },
};

// myDATA API - ΦΠΑ από ΑΑΔΕ
export interface VATRecord {
  id: number;
  afm: string;
  period_year: number;
  period_month: number;
  rec_type: number;  // 1=Εκροές, 2=Εισροές
  vat_category: number;
  amount: number;
  vat_amount: number;
  mark?: string;
  invoice_date?: string;
  counterpart_afm?: string;
  fetched_at: string;
}

export interface VATSummary {
  income_total: number;
  income_vat: number;
  expense_total: number;
  expense_vat: number;
  vat_due: number;
  record_count: number;
}

export interface ClientVATInfo {
  afm: string;
  client_name: string;
  has_credentials: boolean;
  last_sync?: string;
  summary: VATSummary;
  by_category: Array<{
    vat_category: number;
    rec_type: number;
    total_amount: number;
    total_vat: number;
    count: number;
  }>;
}

// Response from /api/mydata/client/{afm}/ endpoint
export interface ClientVATDetailResponse {
  client: {
    afm: string;
    name: string;
  };
  credentials: {
    has_credentials: boolean;
    is_verified: boolean;
    last_sync: string | null;
  };
  period: {
    year: number;
    month: number | null;
    quarter: number | null;
    period_type: string;
    date_from: string;
    date_to: string;
    label: string;
  };
  summary: {
    income_net: number;
    income_vat: number;
    income_count: number;
    expense_net: number;
    expense_vat: number;
    expense_count: number;
    vat_difference: number;
    year?: number;
    month?: number;
    quarter?: number;
    period_type?: string;
    date_from?: string;
    date_to?: string;
  };
  income_by_category: Array<{
    vat_category: number;
    vat_rate: number;
    vat_rate_display: string;
    net_value: number;
    vat_amount: number;
    count: number;
  }>;
  expense_by_category: Array<{
    vat_category: number;
    vat_rate: number;
    vat_rate_display: string;
    net_value: number;
    vat_amount: number;
    count: number;
  }>;
}

export interface MyDataDashboardResponse {
  period: {
    year: number;
    month: number;
  };
  totals: VATSummary;
  clients: ClientVATInfo[];
  sync_status: {
    total_clients: number;
    synced_clients: number;
    pending_clients: number;
    failed_clients: number;
  };
}

export interface TrendData {
  period: string;
  income: number;
  expense: number;
  vat_due: number;
}

export const mydataApi = {
  // Dashboard overview
  getDashboard: async (year?: number, month?: number): Promise<MyDataDashboardResponse> => {
    const params: Record<string, number> = {};
    if (year) params.year = year;
    if (month) params.month = month;
    const response = await apiClient.get('api/mydata/dashboard/', { params });
    return response.data;
  },

  // Monthly trend data for charts
  getTrend: async (months: number = 6): Promise<TrendData[]> => {
    const response = await apiClient.get('api/mydata/trend/', { params: { months } });
    return response.data;
  },

  // Client VAT details
  getClientVAT: async (afm: string, year?: number, month?: number): Promise<ClientVATDetailResponse> => {
    const params: Record<string, number> = {};
    if (year) params.year = year;
    if (month) params.month = month;
    const response = await apiClient.get(`api/mydata/client/${afm}/`, { params });
    return response.data;
  },

  // VAT Records
  getRecords: async (params?: {
    afm?: string;
    year?: number;
    month?: number;
    rec_type?: number;
    page?: number;
  }) => {
    const response = await apiClient.get('api/mydata/records/', { params });
    return response.data;
  },

  // Get records summary
  getRecordsSummary: async (params?: { afm?: string; year?: number; month?: number }) => {
    const response = await apiClient.get('api/mydata/records/summary/', { params });
    return response.data;
  },

  // Get records by VAT category
  getRecordsByCategory: async (params?: { afm?: string; year?: number; month?: number }) => {
    const response = await apiClient.get('api/mydata/records/by_category/', { params });
    return response.data;
  },

  // Credentials management
  credentials: {
    getAll: async () => {
      const response = await apiClient.get('api/mydata/credentials/');
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`api/mydata/credentials/${id}/`);
      return response.data;
    },

    create: async (data: { client: number; mydata_user_id: string; mydata_subscription_key: string }) => {
      const response = await apiClient.post('api/mydata/credentials/', data);
      return response.data;
    },

    update: async (id: number, data: { mydata_user_id?: string; mydata_subscription_key?: string; is_active?: boolean }) => {
      const response = await apiClient.post(`api/mydata/credentials/${id}/update_credentials/`, data);
      return response.data;
    },

    verify: async (id: number) => {
      const response = await apiClient.post(`api/mydata/credentials/${id}/verify/`);
      return response.data;
    },

    sync: async (id: number, year?: number, month?: number) => {
      const data: Record<string, number> = {};
      if (year) data.year = year;
      if (month) data.month = month;
      const response = await apiClient.post(`api/mydata/credentials/${id}/sync/`, data);
      return response.data;
    },

    setInitialCredit: async (id: number, data: {
      initial_credit_balance: number;
      initial_credit_period_year?: number;
      initial_credit_period?: number;
    }) => {
      const response = await apiClient.post(`api/mydata/credentials/${id}/set_initial_credit/`, data);
      return response.data;
    },

    getByClient: async (clientId: number) => {
      const response = await apiClient.get(`api/mydata/credentials/by-client/${clientId}/`);
      return response.data;
    },
  },

  // Sync logs
  getLogs: async (params?: { client?: number; page?: number }) => {
    const response = await apiClient.get('api/mydata/logs/', { params });
    return response.data;
  },

  // VAT Period Results - Υπολογισμός ΦΠΑ ανά περίοδο
  periods: {
    getAll: async (params?: {
      client?: number;
      afm?: string;
      period_type?: 'monthly' | 'quarterly';
      year?: number;
    }) => {
      const response = await apiClient.get('api/mydata/periods/', { params });
      return response.data;
    },

    get: async (id: number) => {
      const response = await apiClient.get(`api/mydata/periods/${id}/`);
      return response.data;
    },

    create: async (data: {
      client: number;
      period_type: 'monthly' | 'quarterly';
      year: number;
      period: number;
      previous_credit?: number;
    }) => {
      const response = await apiClient.post('api/mydata/periods/', data);
      return response.data;
    },

    calculate: async (id: number, syncFirst: boolean = false) => {
      const response = await apiClient.post(`api/mydata/periods/${id}/calculate/`, {
        sync_first: syncFirst,
      });
      return response.data;
    },

    lock: async (id: number) => {
      const response = await apiClient.post(`api/mydata/periods/${id}/lock/`);
      return response.data;
    },

    unlock: async (id: number) => {
      const response = await apiClient.post(`api/mydata/periods/${id}/unlock/`);
      return response.data;
    },

    setCredit: async (id: number, previousCredit: number) => {
      const response = await apiClient.post(`api/mydata/periods/${id}/set_credit/`, {
        previous_credit: previousCredit,
      });
      return response.data;
    },
  },

  // Quick calculator
  calculator: async (params: {
    client_id?: number;
    afm?: string;
    period_type: 'monthly' | 'quarterly';
    year: number;
    period: number;
    recalculate?: boolean;
  }) => {
    const response = await apiClient.get('api/mydata/calculator/', { params });
    return response.data;
  },

  // Τιμολόγια — αποστολή/ακύρωση στο myDATA
  invoices: {
    getAll: async (params?: {
      direction?: 'outgoing' | 'incoming' | 'all';
      mydata_sent?: boolean;
      year?: number;
      page?: number;
    }): Promise<{ results: MyDataInvoice[]; count: number } | MyDataInvoice[]> => {
      const response = await apiClient.get('api/mydata/invoices/', { params });
      return response.data;
    },

    send: async (id: number): Promise<{ success: boolean; mark: number; uid: string; invoice: MyDataInvoice }> => {
      const response = await apiClient.post(`api/mydata/invoices/${id}/send/`);
      return response.data;
    },

    cancel: async (id: number): Promise<{ success: boolean; cancellation_mark: number; invoice: MyDataInvoice }> => {
      const response = await apiClient.post(`api/mydata/invoices/${id}/cancel/`);
      return response.data;
    },
  },
};

export interface MyDataInvoiceItem {
  line_number: number;
  description: string;
  quantity: string;
  net_value: string;
  vat_category: number;
  vat_amount: string;
}

export interface MyDataInvoice {
  id: number;
  series: string;
  number: string;
  invoice_type: string;
  invoice_type_display: string;
  issue_date: string;
  counterpart_name: string;
  counterpart_vat: string;
  is_outgoing: boolean;
  total_net: string;
  total_vat: string;
  total_gross: string;
  mydata_mark: number | null;
  mydata_uid: string;
  mydata_sent: boolean;
  mydata_sent_at: string | null;
  mydata_cancelled: boolean;
  mydata_cancellation_mark: number | null;
  correlated_mark: number | null;
  notes: string;
  items: MyDataInvoiceItem[];
}

// Backup API
export interface BackupItem {
  id: number;
  filename: string;
  file_size: number;
  file_size_display: string;
  includes_db: boolean;
  includes_media: boolean;
  created_at: string;
  created_by?: string;
  notes: string;
  restored_at?: string;
  file_exists: boolean;
}

export interface BackupSettings {
  backup_path: string;
  include_media: boolean;
  max_backups: number;
}

export interface BackupCreateResponse {
  status: string;
  backup: {
    id: number;
    filename: string;
    file_size: number;
    file_size_display: string;
  };
}

export interface BackupRestoreResponse {
  status: string;
  mode: string;
  safety_backup_id?: number;
  backup_id?: number;
}

export const backupApi = {
  // Get backup settings
  getSettings: async (): Promise<BackupSettings> => {
    const response = await apiClient.get('api/settings/backup/settings/');
    return response.data;
  },

  // Update backup settings
  updateSettings: async (data: Partial<BackupSettings>): Promise<{ status: string }> => {
    const response = await apiClient.patch('api/settings/backup/settings/', data);
    return response.data;
  },

  // Get list of backups
  getList: async (): Promise<BackupItem[]> => {
    const response = await apiClient.get('api/settings/backup/list/');
    return response.data;
  },

  // Create a new backup
  create: async (data?: { notes?: string; include_media?: boolean }): Promise<BackupCreateResponse> => {
    const response = await apiClient.post('api/settings/backup/create/', data || {});
    return response.data;
  },

  // Download backup - returns blob URL
  getDownloadUrl: (id: number): string => {
    const token = localStorage.getItem('accessToken');
    return `${API_BASE_URL}/api/settings/backup/${id}/download/?token=${token}`;
  },

  // Restore backup
  restore: async (id: number, data?: { mode?: 'replace' | 'merge'; create_safety_backup?: boolean }): Promise<BackupRestoreResponse> => {
    const response = await apiClient.post(`api/settings/backup/${id}/restore/`, data || {});
    return response.data;
  },

  // Upload and restore backup
  uploadAndRestore: async (
    file: File,
    data?: { mode?: 'replace' | 'merge'; create_safety_backup?: boolean }
  ): Promise<BackupRestoreResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (data?.mode) formData.append('mode', data.mode);
    if (data?.create_safety_backup !== undefined) {
      formData.append('create_safety_backup', String(data.create_safety_backup));
    }

    const response = await apiClient.post('api/settings/backup/upload-restore/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // Delete backup (if implemented)
  delete: async (id: number): Promise<{ status: string }> => {
    const response = await apiClient.delete(`api/settings/backup/${id}/`);
    return response.data;
  },
};

export default apiClient;
