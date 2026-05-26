/**
 * useFilingSettings.ts
 * Hook for Filing System Settings management
 */

import { useState, useCallback } from 'react';
import axios from 'axios';
import type {
  FilingSystemSettings,
  FolderTreeNode,
  CategoryMeta,
  GroupedCategories,
  UpdateFilingSettingsRequest,
} from '../types/filingSettings';

const API_BASE = '/accounting/settings/api';

// ============================================
// FILING SETTINGS HOOK
// ============================================

export function useFilingSettings() {
  const [settings, setSettings] = useState<FilingSystemSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get<FilingSystemSettings>(`${API_BASE}/filing/`);
      setSettings(response.data);
      return response.data;
    } catch (err: any) {
      const message = err.response?.data?.error || 'Σφάλμα φόρτωσης ρυθμίσεων';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = useCallback(async (data: UpdateFilingSettingsRequest) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.patch<FilingSystemSettings>(`${API_BASE}/filing/`, data);
      setSettings(response.data);
      return response.data;
    } catch (err: any) {
      const message = err.response?.data?.error || 'Σφάλμα αποθήκευσης ρυθμίσεων';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    settings,
    loading,
    error,
    fetchSettings,
    updateSettings,
  };
}

// ============================================
// FOLDER PREVIEW HOOK
// ============================================

export function useFolderPreview() {
  const [structure, setStructure] = useState<FolderTreeNode | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchPreview = useCallback(async (clientId?: number) => {
    setLoading(true);
    try {
      const params = clientId ? { client_id: clientId } : {};
      const response = await axios.get(`${API_BASE}/filing/folder-preview/`, { params });
      setStructure(response.data.structure);
      return response.data.structure;
    } catch (err) {
      console.error('Error fetching folder preview:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  return { structure, loading, fetchPreview };
}

// ============================================
// CATEGORIES HOOK
// ============================================

export function useDocumentCategories() {
  const [categories, setCategories] = useState<CategoryMeta[]>([]);
  const [grouped, setGrouped] = useState<GroupedCategories | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/filing/categories/`);
      setCategories(response.data.categories);
      setGrouped(response.data.grouped);
      return response.data;
    } catch (err) {
      console.error('Error fetching categories:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const getCategoryMeta = useCallback((code: string): CategoryMeta | undefined => {
    return categories.find(c => c.value === code);
  }, [categories]);

  return { categories, grouped, loading, fetchCategories, getCategoryMeta };
}

// ============================================
// FOLDER BROWSER HOOK (Extended)
// ============================================

interface BrowseState {
  clients: { id: number; eponimia: string; afm: string; document_count: number }[];
  years: { year: number; count: number }[];
  months: { month: number; count: number }[];
  currentClient: { id: number; eponimia: string } | null;
  currentYear: number | null;
  currentMonth: number | null;
  currentCategory: string | null;
}

export function useFolderBrowser() {
  const [state, setState] = useState<BrowseState>({
    clients: [],
    years: [],
    months: [],
    currentClient: null,
    currentYear: null,
    currentMonth: null,
    currentCategory: null,
  });
  const [loading, setLoading] = useState(false);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get('/accounting/api/v1/file-manager/browse/');
      if (response.data.type === 'clients') {
        setState(prev => ({
          ...prev,
          clients: response.data.clients,
          currentClient: null,
          currentYear: null,
          currentMonth: null,
          years: [],
          months: [],
        }));
      }
    } catch (err) {
      console.error('Error fetching clients:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchYears = useCallback(async (clientId: number) => {
    setLoading(true);
    try {
      const response = await axios.get('/accounting/api/v1/file-manager/browse/', {
        params: { client_id: clientId }
      });
      if (response.data.type === 'years') {
        setState(prev => ({
          ...prev,
          currentClient: response.data.client,
          currentYear: null,
          currentMonth: null,
          years: response.data.years,
          months: [],
        }));
      }
    } catch (err) {
      console.error('Error fetching years:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMonths = useCallback(async (clientId: number, year: number) => {
    setLoading(true);
    try {
      const response = await axios.get('/accounting/api/v1/file-manager/browse/', {
        params: { client_id: clientId, year }
      });
      if (response.data.type === 'months') {
        setState(prev => ({
          ...prev,
          currentYear: year,
          currentMonth: null,
          months: response.data.months,
        }));
      }
    } catch (err) {
      console.error('Error fetching months:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const navigateToClient = useCallback((clientId: number) => {
    fetchYears(clientId);
  }, [fetchYears]);

  const navigateToYear = useCallback((year: number) => {
    if (state.currentClient) {
      fetchMonths(state.currentClient.id, year);
    }
  }, [state.currentClient, fetchMonths]);

  const navigateToMonth = useCallback((month: number) => {
    setState(prev => ({ ...prev, currentMonth: month }));
  }, []);

  const navigateToCategory = useCallback((category: string) => {
    setState(prev => ({ ...prev, currentCategory: category }));
  }, []);

  const navigateBack = useCallback(() => {
    if (state.currentCategory) {
      setState(prev => ({ ...prev, currentCategory: null }));
    } else if (state.currentMonth !== null) {
      setState(prev => ({ ...prev, currentMonth: null }));
    } else if (state.currentYear !== null) {
      setState(prev => ({ ...prev, currentYear: null, months: [] }));
    } else if (state.currentClient) {
      fetchClients();
    }
  }, [state, fetchClients]);

  const getBreadcrumbs = useCallback(() => {
    const crumbs: { label: string; onClick?: () => void }[] = [
      { label: 'Πελάτες', onClick: fetchClients }
    ];

    if (state.currentClient) {
      crumbs.push({
        label: state.currentClient.eponimia,
        onClick: () => navigateToClient(state.currentClient!.id)
      });
    }

    if (state.currentYear !== null) {
      crumbs.push({
        label: String(state.currentYear),
        onClick: () => navigateToYear(state.currentYear!)
      });
    }

    if (state.currentMonth !== null) {
      const monthNames = [
        'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος',
        'Μάιος', 'Ιούνιος', 'Ιούλιος', 'Αύγουστος',
        'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος'
      ];
      crumbs.push({
        label: monthNames[state.currentMonth - 1],
        onClick: () => navigateToMonth(state.currentMonth!)
      });
    }

    if (state.currentCategory) {
      crumbs.push({ label: state.currentCategory });
    }

    return crumbs;
  }, [state, fetchClients, navigateToClient, navigateToYear, navigateToMonth]);

  return {
    ...state,
    loading,
    fetchClients,
    navigateToClient,
    navigateToYear,
    navigateToMonth,
    navigateToCategory,
    navigateBack,
    getBreadcrumbs,
  };
}

export default useFilingSettings;
