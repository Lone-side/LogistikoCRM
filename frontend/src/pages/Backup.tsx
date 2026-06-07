import { useState, useEffect, useRef } from 'react';
import {
  Database,
  Download,
  Upload,
  RotateCcw,
  Plus,
  Check,
  X,
  Loader2,
  AlertTriangle,
  HardDrive,
  FileArchive,
  Clock,
  Settings,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../components';
import { useToast } from '../components/Toast';
import { backupApi, type BackupItem, type BackupSettings } from '../api/client';

export default function Backup() {
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // State
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [, setSettings] = useState<BackupSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);
  const [uploadingRestore, setUploadingRestore] = useState(false);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [selectedBackup, setSelectedBackup] = useState<BackupItem | null>(null);

  // Form states
  const [createNotes, setCreateNotes] = useState('');
  const [createIncludeMedia, setCreateIncludeMedia] = useState(true);
  const [restoreMode, setRestoreMode] = useState<'replace' | 'merge'>('replace');
  const [createSafetyBackup, setCreateSafetyBackup] = useState(true);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Settings form
  const [settingsForm, setSettingsForm] = useState({
    backup_path: '',
    include_media: true,
    max_backups: 10,
  });

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [backupList, backupSettings] = await Promise.all([
        backupApi.getList(),
        backupApi.getSettings(),
      ]);
      setBackups(backupList);
      setSettings(backupSettings);
      setSettingsForm({
        backup_path: backupSettings.backup_path,
        include_media: backupSettings.include_media,
        max_backups: backupSettings.max_backups,
      });
    } catch (error) {
      console.error('Failed to load backup data:', error);
      showToast('error', 'Σφάλμα φόρτωσης δεδομένων');
    } finally {
      setLoading(false);
    }
  };

  // Create backup
  const handleCreateBackup = async () => {
    setCreating(true);
    try {
      const response = await backupApi.create({
        notes: createNotes || undefined,
        include_media: createIncludeMedia,
      });
      showToast('success', `Backup δημιουργήθηκε: ${response.backup.filename}`);
      setShowCreateModal(false);
      setCreateNotes('');
      loadData();
    } catch (error) {
      console.error('Create backup failed:', error);
      showToast('error', 'Σφάλμα δημιουργίας backup');
    } finally {
      setCreating(false);
    }
  };

  // Restore backup
  const handleRestore = async () => {
    if (!selectedBackup) return;

    setRestoringId(selectedBackup.id);
    try {
      const response = await backupApi.restore(selectedBackup.id, {
        mode: restoreMode,
        create_safety_backup: createSafetyBackup,
      });

      let message = 'Backup επαναφέρθηκε επιτυχώς';
      if (response.safety_backup_id) {
        message += ` (Safety backup ID: ${response.safety_backup_id})`;
      }
      showToast('success', message);
      setShowRestoreModal(false);
      loadData();
    } catch (error) {
      console.error('Restore failed:', error);
      showToast('error', 'Σφάλμα επαναφοράς backup');
    } finally {
      setRestoringId(null);
    }
  };

  // Upload and restore
  const handleUploadRestore = async () => {
    if (!uploadFile) return;

    setUploadingRestore(true);
    try {
      const response = await backupApi.uploadAndRestore(uploadFile, {
        mode: restoreMode,
        create_safety_backup: createSafetyBackup,
      });

      let message = 'Backup ανέβηκε και επαναφέρθηκε επιτυχώς';
      if (response.safety_backup_id) {
        message += ` (Safety backup ID: ${response.safety_backup_id})`;
      }
      showToast('success', message);
      setShowUploadModal(false);
      setUploadFile(null);
      loadData();
    } catch (error: unknown) {
      console.error('Upload restore failed:', error);
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? (error as { response?: { data?: { error?: string } } }).response?.data?.error || 'Σφάλμα'
        : 'Σφάλμα upload/restore';
      showToast('error', errorMessage);
    } finally {
      setUploadingRestore(false);
    }
  };

  // Save settings
  const handleSaveSettings = async () => {
    try {
      await backupApi.updateSettings(settingsForm);
      showToast('success', 'Οι ρυθμίσεις αποθηκεύτηκαν');
      setShowSettingsModal(false);
      loadData();
    } catch (error) {
      console.error('Save settings failed:', error);
      showToast('error', 'Σφάλμα αποθήκευσης ρυθμίσεων');
    }
  };

  // Download backup
  const handleDownload = (backup: BackupItem) => {
    const url = backupApi.getDownloadUrl(backup.id);
    window.open(url, '_blank');
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('el-GR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Format file size
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-brand-600" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Backup & Restore</h1>
          <p className="text-gray-500 mt-1">Διαχείριση αντιγράφων ασφαλείας</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowSettingsModal(true)}>
            <Settings size={18} className="mr-2" />
            Ρυθμίσεις
          </Button>
          <Button variant="secondary" onClick={() => setShowUploadModal(true)}>
            <Upload size={18} className="mr-2" />
            Upload & Restore
          </Button>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus size={18} className="mr-2" />
            Νέο Backup
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
              <Database size={20} className="text-brand-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{backups.length}</p>
              <p className="text-sm text-gray-500">Συνολικά Backups</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Check size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {backups.filter(b => b.file_exists).length}
              </p>
              <p className="text-sm text-gray-500">Διαθέσιμα</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <HardDrive size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {formatSize(backups.reduce((sum, b) => sum + (b.file_exists ? b.file_size : 0), 0))}
              </p>
              <p className="text-sm text-gray-500">Συνολικό Μέγεθος</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <Clock size={20} className="text-orange-600" />
            </div>
            <div>
              <p className="text-sm font-bold text-gray-900">
                {backups[0] ? formatDate(backups[0].created_at) : '-'}
              </p>
              <p className="text-sm text-gray-500">Τελευταίο Backup</p>
            </div>
          </div>
        </div>
      </div>

      {/* Backup List */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Λίστα Backups</h2>
          <Button variant="secondary" size="sm" onClick={loadData}>
            <RefreshCw size={16} className="mr-1" />
            Ανανέωση
          </Button>
        </div>

        {backups.length === 0 ? (
          <div className="p-12 text-center">
            <FileArchive size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">Δεν υπάρχουν backups</p>
            <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
              <Plus size={18} className="mr-2" />
              Δημιουργία πρώτου backup
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Αρχείο
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Μέγεθος
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Περιεχόμενα
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Ημερομηνία
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Κατάσταση
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Ενέργειες
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {backups.map((backup) => (
                  <tr key={backup.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <FileArchive size={20} className="text-gray-400" />
                        <div>
                          <p className="font-medium text-gray-900">{backup.filename}</p>
                          {backup.notes && (
                            <p className="text-sm text-gray-500">{backup.notes}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {backup.file_size_display || formatSize(backup.file_size)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        {backup.includes_db && (
                          <span className="px-2 py-1 text-xs bg-brand-100 text-brand-700 rounded">
                            DB
                          </span>
                        )}
                        {backup.includes_media && (
                          <span className="px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded">
                            Media
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {formatDate(backup.created_at)}
                      {backup.restored_at && (
                        <p className="text-xs text-green-600 mt-1">
                          Restored: {formatDate(backup.restored_at)}
                        </p>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {backup.file_exists ? (
                        <span className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded flex items-center gap-1 w-fit">
                          <Check size={12} />
                          Διαθέσιμο
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded flex items-center gap-1 w-fit">
                          <X size={12} />
                          Μη διαθέσιμο
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {backup.file_exists && (
                          <>
                            <button
                              onClick={() => handleDownload(backup)}
                              className="p-2 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
                              title="Download"
                            >
                              <Download size={18} />
                            </button>
                            <button
                              onClick={() => {
                                setSelectedBackup(backup);
                                setShowRestoreModal(true);
                              }}
                              disabled={restoringId === backup.id}
                              className="p-2 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors disabled:opacity-50"
                              title="Restore"
                            >
                              {restoringId === backup.id ? (
                                <Loader2 size={18} className="animate-spin" />
                              ) : (
                                <RotateCcw size={18} />
                              )}
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Backup Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Δημιουργία Backup</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Σημειώσεις (προαιρετικό)
                </label>
                <input
                  type="text"
                  value={createNotes}
                  onChange={(e) => setCreateNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                  placeholder="π.χ. Πριν την αναβάθμιση"
                />
              </div>

              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Συμπερίληψη Media</p>
                  <p className="text-sm text-gray-500">Uploaded αρχεία πελατών</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={createIncludeMedia}
                    onChange={(e) => setCreateIncludeMedia(e.target.checked)}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
                Ακύρωση
              </Button>
              <Button onClick={handleCreateBackup} disabled={creating}>
                {creating ? (
                  <>
                    <Loader2 size={18} className="animate-spin mr-2" />
                    Δημιουργία...
                  </>
                ) : (
                  <>
                    <Database size={18} className="mr-2" />
                    Δημιουργία Backup
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Restore Modal */}
      {showRestoreModal && selectedBackup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Επαναφορά Backup</h3>
              <button onClick={() => setShowRestoreModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Warning */}
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex gap-3">
                <AlertTriangle className="text-yellow-600 flex-shrink-0" size={20} />
                <div className="text-sm text-yellow-800">
                  <p className="font-medium">Προσοχή!</p>
                  <p>Η επαναφορά με mode "Αντικατάσταση" θα διαγράψει τα τρέχοντα δεδομένα.</p>
                </div>
              </div>

              {/* Backup info */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="font-medium text-gray-900">{selectedBackup.filename}</p>
                <p className="text-sm text-gray-500">
                  {formatDate(selectedBackup.created_at)} · {selectedBackup.file_size_display || formatSize(selectedBackup.file_size)}
                </p>
              </div>

              {/* Mode selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Τρόπος επαναφοράς</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                    <input
                      type="radio"
                      name="restoreMode"
                      value="replace"
                      checked={restoreMode === 'replace'}
                      onChange={() => setRestoreMode('replace')}
                      className="text-brand-600"
                    />
                    <div>
                      <p className="font-medium text-gray-900">Αντικατάσταση</p>
                      <p className="text-sm text-gray-500">Διαγραφή υπαρχόντων και φόρτωση backup</p>
                    </div>
                  </label>
                  <label className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                    <input
                      type="radio"
                      name="restoreMode"
                      value="merge"
                      checked={restoreMode === 'merge'}
                      onChange={() => setRestoreMode('merge')}
                      className="text-brand-600"
                    />
                    <div>
                      <p className="font-medium text-gray-900">Συγχώνευση</p>
                      <p className="text-sm text-gray-500">Προσθήκη δεδομένων χωρίς διαγραφή</p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Safety backup option */}
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Safety Backup</p>
                  <p className="text-sm text-gray-500">Δημιουργία backup πριν την επαναφορά</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={createSafetyBackup}
                    onChange={(e) => setCreateSafetyBackup(e.target.checked)}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <Button variant="secondary" onClick={() => setShowRestoreModal(false)}>
                Ακύρωση
              </Button>
              <Button onClick={handleRestore} disabled={restoringId !== null}>
                {restoringId !== null ? (
                  <>
                    <Loader2 size={18} className="animate-spin mr-2" />
                    Επαναφορά...
                  </>
                ) : (
                  <>
                    <RotateCcw size={18} className="mr-2" />
                    Επαναφορά
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Upload & Restore Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Upload & Restore</h3>
              <button onClick={() => { setShowUploadModal(false); setUploadFile(null); }} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Warning */}
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex gap-3">
                <AlertTriangle className="text-yellow-600 flex-shrink-0" size={20} />
                <div className="text-sm text-yellow-800">
                  <p className="font-medium">Προσοχή!</p>
                  <p>Ανεβάστε μόνο backup αρχεία από αξιόπιστη πηγή.</p>
                </div>
              </div>

              {/* File input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Αρχείο Backup (ZIP)</label>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".zip"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                />
                {uploadFile && (
                  <p className="text-sm text-gray-500 mt-1">
                    {uploadFile.name} ({formatSize(uploadFile.size)})
                  </p>
                )}
              </div>

              {/* Mode selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Τρόπος επαναφοράς</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                    <input
                      type="radio"
                      name="uploadRestoreMode"
                      value="replace"
                      checked={restoreMode === 'replace'}
                      onChange={() => setRestoreMode('replace')}
                      className="text-brand-600"
                    />
                    <div>
                      <p className="font-medium text-gray-900">Αντικατάσταση</p>
                      <p className="text-sm text-gray-500">Διαγραφή υπαρχόντων</p>
                    </div>
                  </label>
                  <label className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                    <input
                      type="radio"
                      name="uploadRestoreMode"
                      value="merge"
                      checked={restoreMode === 'merge'}
                      onChange={() => setRestoreMode('merge')}
                      className="text-brand-600"
                    />
                    <div>
                      <p className="font-medium text-gray-900">Συγχώνευση</p>
                      <p className="text-sm text-gray-500">Προσθήκη χωρίς διαγραφή</p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Safety backup option */}
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Safety Backup</p>
                  <p className="text-sm text-gray-500">Δημιουργία backup πριν την επαναφορά</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={createSafetyBackup}
                    onChange={(e) => setCreateSafetyBackup(e.target.checked)}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <Button variant="secondary" onClick={() => { setShowUploadModal(false); setUploadFile(null); }}>
                Ακύρωση
              </Button>
              <Button onClick={handleUploadRestore} disabled={!uploadFile || uploadingRestore}>
                {uploadingRestore ? (
                  <>
                    <Loader2 size={18} className="animate-spin mr-2" />
                    Επεξεργασία...
                  </>
                ) : (
                  <>
                    <Upload size={18} className="mr-2" />
                    Upload & Restore
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Ρυθμίσεις Backup</h3>
              <button onClick={() => setShowSettingsModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Φάκελος Backup
                </label>
                <input
                  type="text"
                  value={settingsForm.backup_path}
                  onChange={(e) => setSettingsForm({ ...settingsForm, backup_path: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                />
                <p className="text-xs text-gray-500 mt-1">Σχετικό path από MEDIA_ROOT</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Μέγιστος αριθμός Backups
                </label>
                <input
                  type="number"
                  min="0"
                  value={settingsForm.max_backups}
                  onChange={(e) => setSettingsForm({ ...settingsForm, max_backups: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-brand-500"
                />
                <p className="text-xs text-gray-500 mt-1">0 = χωρίς όριο</p>
              </div>

              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Default: Συμπερίληψη Media</p>
                  <p className="text-sm text-gray-500">Στα νέα backups</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={settingsForm.include_media}
                    onChange={(e) => setSettingsForm({ ...settingsForm, include_media: e.target.checked })}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <Button variant="secondary" onClick={() => setShowSettingsModal(false)}>
                Ακύρωση
              </Button>
              <Button onClick={handleSaveSettings}>
                <Settings size={18} className="mr-2" />
                Αποθήκευση
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
