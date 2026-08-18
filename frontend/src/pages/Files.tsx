import { useState } from 'react';
import { FolderOpen, Upload, Search, Filter, ExternalLink, Settings, Users, FileText } from 'lucide-react';
import { Button } from '../components';
import { PageHeader } from '../components/ui';
import { useClients } from '../hooks/useClients';
import type { Client } from '../types';

export default function Files() {
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);

  const { data: clientsData, isLoading, isError } = useClients({
    page,
    page_size: 20,
    search: searchTerm || undefined,
  });

  const clients = clientsData?.results || [];
  const totalPages = clientsData ? Math.ceil(clientsData.count / 20) : 1;

  const handleSearch = (value: string) => {
    setSearchTerm(value);
    setPage(1); // Reset to first page on search
  };

  const openClientFolder = (clientId: number) => {
    // Opens the Django client files view in a new tab
    window.open(`/accounting/client/${clientId}/files/`, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Αρχεία Πελατών"
        subtitle="Πρόσβαση στους φακέλους αρχειοθέτησης"
        actions={
          <>
            <a
              href="/accounting/settings/archive/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors duration-150"
            >
              <Settings size={18} className="mr-2" />
              Ρυθμίσεις
            </a>
            <Button onClick={() => window.open('/admin/accounting/clientdocument/add/', '_blank')}>
              <Upload size={18} className="mr-2" />
              Νέο Έγγραφο
            </Button>
          </>
        }
      />

      {/* Quick Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-brand-100 rounded-lg flex items-center justify-center">
              <Users size={24} className="text-brand-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{clientsData?.count || 0}</p>
              <p className="text-sm text-slate-500">Πελάτες</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
              <FolderOpen size={24} className="text-success-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">-</p>
              <p className="text-sm text-slate-500">Φάκελοι</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <FileText size={24} className="text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">-</p>
              <p className="text-sm text-slate-500">Έγγραφα</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Αναζήτηση πελάτη (ΑΦΜ, επωνυμία)..."
              aria-label="Αναζήτηση πελάτη"
              value={searchTerm}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors duration-150">
            <Filter size={18} />
            <span>Φίλτρα</span>
          </button>
        </div>
      </div>

      {/* Clients List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="p-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">Φάκελοι Πελατών</h2>
          <p className="text-sm text-slate-500 mt-1">
            Κάντε κλικ για να ανοίξετε τον φάκελο αρχειοθέτησης
          </p>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-slate-500">
            <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            Φόρτωση πελατών...
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-danger-600">
            Σφάλμα κατά τη φόρτωση των πελατών
          </div>
        ) : clients.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <FolderOpen size={32} className="text-slate-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              {searchTerm ? 'Δεν βρέθηκαν πελάτες' : 'Δεν υπάρχουν πελάτες'}
            </h3>
            <p className="text-slate-500 max-w-md mx-auto">
              {searchTerm
                ? 'Δοκιμάστε με διαφορετικούς όρους αναζήτησης'
                : 'Προσθέστε πελάτες για να δημιουργηθούν οι φάκελοι αρχειοθέτησης'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {clients.map((client: Client) => (
              <div
                key={client.id}
                className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors duration-150 cursor-pointer"
                onClick={() => openClientFolder(client.id)}
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-teal-100 rounded-lg flex items-center justify-center">
                    <FolderOpen size={20} className="text-teal-600" />
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">{client.eponimia}</p>
                    <p className="text-sm text-slate-500">ΑΦΜ: {client.afm}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {client.total_obligations !== undefined && client.total_obligations > 0 && (
                    <span className="px-2 py-1 bg-brand-100 text-brand-700 text-xs font-medium rounded">
                      {client.total_obligations} υποχρεώσεις
                    </span>
                  )}
                  <ExternalLink size={18} className="text-slate-400" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
            <div className="text-sm text-slate-500">
              Σελίδα {page} από {totalPages} ({clientsData?.count} πελάτες)
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-150"
              >
                Προηγούμενη
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-150"
              >
                Επόμενη
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Feature Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="w-10 h-10 bg-success-100 rounded-lg flex items-center justify-center mb-4">
            <FolderOpen size={20} className="text-success-600" />
          </div>
          <h4 className="font-semibold text-slate-900 mb-2">Οργάνωση φακέλων</h4>
          <p className="text-sm text-slate-500">
            Αυτόματη δημιουργία φακέλων ανά πελάτη, έτος, μήνα και τύπο υποχρέωσης
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
            <Search size={20} className="text-purple-600" />
          </div>
          <h4 className="font-semibold text-slate-900 mb-2">Γρήγορη αναζήτηση</h4>
          <p className="text-sm text-slate-500">
            Βρείτε αρχεία με ΑΦΜ, επωνυμία ή τύπο υποχρέωσης
          </p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
            <Upload size={20} className="text-orange-600" />
          </div>
          <h4 className="font-semibold text-slate-900 mb-2">Εύκολη μεταφόρτωση</h4>
          <p className="text-sm text-slate-500">
            Ανεβάστε αρχεία απευθείας στις υποχρεώσεις
          </p>
        </div>
      </div>
    </div>
  );
}
