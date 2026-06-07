/**
 * FilingSettings.tsx
 * Settings page for Filing System configuration
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderTree,
  Save,
  RefreshCw,
  HardDrive,
  Network,
  FileText,
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  Info,
  ChevronLeft,
} from 'lucide-react';
import { MiniTreePreview } from '../components/FolderTreeView';
import { useFilingSettings, useFolderPreview } from '../hooks/useFilingSettings';
import type { FilingSystemSettings } from '../types/filingSettings';
import {
  FOLDER_STRUCTURE_CHOICES,
  FILE_NAMING_CHOICES,
} from '../types/filingSettings';

const FilingSettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { settings, loading, error, fetchSettings, updateSettings } = useFilingSettings();
  const { structure, fetchPreview } = useFolderPreview();

  // Form state
  const [formData, setFormData] = useState<Partial<FilingSystemSettings>>({});
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Load settings on mount
  useEffect(() => {
    fetchSettings();
    fetchPreview();
  }, [fetchSettings, fetchPreview]);

  // Update form when settings load
  useEffect(() => {
    if (settings) {
      setFormData(settings);
    }
  }, [settings]);

  // Refresh preview when folder settings change
  useEffect(() => {
    if (formData.folder_structure || formData.use_greek_month_names !== undefined) {
      // Debounce preview update
      const timer = setTimeout(() => fetchPreview(), 500);
      return () => clearTimeout(timer);
    }
  }, [formData.folder_structure, formData.use_greek_month_names, fetchPreview]);

  const handleChange = (field: keyof FilingSystemSettings, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setSaveSuccess(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      await updateSettings(formData);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setSaveError(err.response?.data?.error || 'Σφάλμα αποθήκευσης');
    } finally {
      setSaving(false);
    }
  };

  if (loading && !settings) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/settings')}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <FolderTree className="w-6 h-6 text-brand-600" />
                Ρυθμίσεις Αρχειοθέτησης
              </h1>
              <p className="text-gray-500 text-sm mt-1">
                Διαχείριση δομής φακέλων και κανόνων αρχειοθέτησης
              </p>
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Αποθήκευση
          </button>
        </div>

        {/* Success/Error Messages */}
        {saveSuccess && (
          <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2 text-green-700 dark:text-green-400">
            <CheckCircle className="w-5 h-5" />
            Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς
          </div>
        )}

        {(error || saveError) && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2 text-red-700 dark:text-red-400">
            <AlertTriangle className="w-5 h-5" />
            {error || saveError}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Settings Forms */}
          <div className="lg:col-span-2 space-y-6">
            {/* Storage Location */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <HardDrive className="w-5 h-5 text-gray-600" />
                Τοποθεσία Αποθήκευσης
              </h2>

              <div className="space-y-4">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={formData.use_network_storage || false}
                    onChange={(e) => handleChange('use_network_storage', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                  />
                  <div>
                    <span className="font-medium flex items-center gap-2">
                      <Network className="w-4 h-4" />
                      Χρήση Δικτυακού Φακέλου
                    </span>
                    <span className="text-sm text-gray-500 block">
                      Αποθήκευση αρχείων σε κοινόχρηστο φάκελο δικτύου (NAS/Server)
                    </span>
                  </div>
                </label>

                {formData.use_network_storage && (
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Διαδρομή Δικτύου
                    </label>
                    <input
                      type="text"
                      value={formData.archive_root || ''}
                      onChange={(e) => handleChange('archive_root', e.target.value)}
                      placeholder="/mnt/nas/logistiko/ ή Z:\Logistiko\"
                      className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-600"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Παραδείγματα: /mnt/nas/logistiko/ (Linux), Z:\Logistiko\ (Windows)
                    </p>
                  </div>
                )}
              </div>
            </section>

            {/* Folder Structure */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <FolderTree className="w-5 h-5 text-gray-600" />
                Δομή Φακέλων
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Τρόπος Οργάνωσης
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {FOLDER_STRUCTURE_CHOICES.map((choice) => (
                      <label
                        key={choice.value}
                        className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                          formData.folder_structure === choice.value
                            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
                        }`}
                      >
                        <input
                          type="radio"
                          name="folder_structure"
                          value={choice.value}
                          checked={formData.folder_structure === choice.value}
                          onChange={(e) => handleChange('folder_structure', e.target.value)}
                          className="mt-1"
                        />
                        <div>
                          <span className="font-medium block">{choice.label}</span>
                          <span className="text-xs text-gray-500">{choice.description}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {formData.folder_structure === 'custom' && (
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Custom Template
                    </label>
                    <input
                      type="text"
                      value={formData.custom_folder_template || ''}
                      onChange={(e) => handleChange('custom_folder_template', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg font-mono text-sm dark:bg-gray-800 dark:border-gray-600"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Μεταβλητές: {'{afm}'}, {'{name}'}, {'{year}'}, {'{month}'}, {'{category}'}, {'{month_name}'}
                    </p>
                  </div>
                )}

                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={formData.use_greek_month_names || false}
                    onChange={(e) => handleChange('use_greek_month_names', e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-brand-600"
                  />
                  <div>
                    <span className="font-medium">Ελληνικά Ονόματα Μηνών</span>
                    <span className="text-sm text-gray-500 block">
                      π.χ. 01_Ιανουάριος αντί για 01
                    </span>
                  </div>
                </label>
              </div>
            </section>

            {/* Special Folders */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-gray-600" />
                Ειδικοί Φάκελοι
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Permanent Folder */}
                <div className="space-y-3">
                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={formData.enable_permanent_folder || false}
                      onChange={(e) => handleChange('enable_permanent_folder', e.target.checked)}
                      className="w-5 h-5 rounded border-gray-300 text-purple-600"
                    />
                    <span className="font-medium">Μόνιμος Φάκελος</span>
                  </label>
                  {formData.enable_permanent_folder && (
                    <input
                      type="text"
                      value={formData.permanent_folder_name || ''}
                      onChange={(e) => handleChange('permanent_folder_name', e.target.value)}
                      placeholder="00_ΜΟΝΙΜΑ"
                      className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-600"
                    />
                  )}
                  <p className="text-xs text-gray-500">
                    Για συμβάσεις, ιδρυτικά, άδειες (00_ = εμφανίζεται πρώτος)
                  </p>
                </div>

                {/* Year-End Folder */}
                <div className="space-y-3">
                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={formData.enable_yearend_folder || false}
                      onChange={(e) => handleChange('enable_yearend_folder', e.target.checked)}
                      className="w-5 h-5 rounded border-gray-300 text-amber-600"
                    />
                    <span className="font-medium">Φάκελος Ετήσιων</span>
                  </label>
                  {formData.enable_yearend_folder && (
                    <input
                      type="text"
                      value={formData.yearend_folder_name || ''}
                      onChange={(e) => handleChange('yearend_folder_name', e.target.value)}
                      placeholder="13_ΕΤΗΣΙΑ"
                      className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-600"
                    />
                  )}
                  <p className="text-xs text-gray-500">
                    Για Ε1, Ε2, Ε3, ΕΝΦΙΑ, Ισολογισμό (13_ = μετά τους μήνες)
                  </p>
                </div>
              </div>
            </section>

            {/* File Naming */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <FileText className="w-5 h-5 text-gray-600" />
                Ονοματολογία Αρχείων
              </h2>

              <div className="space-y-2">
                {FILE_NAMING_CHOICES.map((choice) => (
                  <label
                    key={choice.value}
                    className={`flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-colors ${
                      formData.file_naming_convention === choice.value
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="radio"
                        name="file_naming"
                        value={choice.value}
                        checked={formData.file_naming_convention === choice.value}
                        onChange={(e) => handleChange('file_naming_convention', e.target.value)}
                      />
                      <span className="font-medium">{choice.label}</span>
                    </div>
                    <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
                      {choice.example}
                    </code>
                  </label>
                ))}
              </div>
            </section>

            {/* Retention Policy */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <Clock className="w-5 h-5 text-gray-600" />
                Πολιτική Διατήρησης
              </h2>

              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4">
                <p className="text-sm text-amber-800 dark:text-amber-300 flex items-start gap-2">
                  <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  Νόμος 4308/2014: Ελάχιστη διατήρηση 5 έτη, έως 20 έτη σε περίπτωση φοροδιαφυγής
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Έτη Διατήρησης
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="20"
                    value={formData.retention_years || 5}
                    onChange={(e) => handleChange('retention_years', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-600"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Αυτόματη Αρχειοθέτηση
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={formData.auto_archive_years || 0}
                    onChange={(e) => handleChange('auto_archive_years', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-600"
                  />
                  <p className="text-xs text-gray-500 mt-1">0 = απενεργοποιημένο</p>
                </div>

                <div className="flex items-end">
                  <label className="flex items-center gap-2 pb-2">
                    <input
                      type="checkbox"
                      checked={formData.enable_retention_warnings || false}
                      onChange={(e) => handleChange('enable_retention_warnings', e.target.checked)}
                      className="w-5 h-5 rounded border-gray-300 text-brand-600"
                    />
                    <span className="text-sm">Προειδοποιήσεις λήξης</span>
                  </label>
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5 text-gray-600" />
                Ασφάλεια Αρχείων
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Επιτρεπόμενοι Τύποι Αρχείων
                  </label>
                  <textarea
                    value={formData.allowed_extensions || ''}
                    onChange={(e) => handleChange('allowed_extensions', e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 border rounded-lg text-sm font-mono dark:bg-gray-800 dark:border-gray-600"
                    placeholder=".pdf,.xlsx,.docx,..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Μέγιστο Μέγεθος (MB)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.max_file_size_mb || 10}
                    onChange={(e) => handleChange('max_file_size_mb', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-600"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Μέγιστο μέγεθος ανά αρχείο
                  </p>
                </div>
              </div>
            </section>
          </div>

          {/* Preview Sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-6 space-y-4">
              <MiniTreePreview structure={structure} maxHeight="500px" />

              {/* Quick Info */}
              <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="font-semibold mb-3">Σύνοψη Ρυθμίσεων</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Τοποθεσία:</span>
                    <span className="font-medium">
                      {formData.use_network_storage ? 'Δίκτυο' : 'Τοπικά'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Δομή:</span>
                    <span className="font-medium">
                      {FOLDER_STRUCTURE_CHOICES.find(c => c.value === formData.folder_structure)?.label || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Διατήρηση:</span>
                    <span className="font-medium">{formData.retention_years} έτη</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Μέγ. αρχείο:</span>
                    <span className="font-medium">{formData.max_file_size_mb} MB</span>
                  </div>
                </div>
              </div>

              {/* Help */}
              <div className="bg-brand-50 dark:bg-brand-900/20 rounded-xl p-4">
                <h3 className="font-semibold text-brand-800 dark:text-brand-300 mb-2">
                  Βοήθεια
                </h3>
                <ul className="text-sm text-brand-700 dark:text-brand-400 space-y-1">
                  <li>• Η δομή φακέλων εφαρμόζεται σε νέους πελάτες</li>
                  <li>• Τρέξτε init_filing_system για υπάρχοντες</li>
                  <li>• Τα αρχεία δεν μετακινούνται αυτόματα</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
};

export default FilingSettingsPage;
