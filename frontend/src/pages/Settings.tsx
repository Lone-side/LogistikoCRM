import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  User,
  Users,
  Bell,
  Shield,
  Globe,
  Database,
  Mail,
  Phone,
  Save,
  FileText,
  ChevronRight,
  Check,
  X,
  Loader2,
  RefreshCw,
  HardDrive,
  FolderTree,
} from 'lucide-react';
import { Button } from '../components';
import { PageHeader } from '../components/ui';
import { useToast } from '../hooks/useToast';
import { useAuthStore } from '../stores/authStore';
import { gsisApi, authApi } from '../api/client';
import apiClient from '../api/client';

type SettingsTab = 'profile' | 'notifications' | 'security' | 'integrations';

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const { user, setUser } = useAuthStore();
  const { showToast } = useToast();

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
  });
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Notification settings state
  const [notificationSettings, setNotificationSettings] = useState({
    email_reminders: true,
    email_overdue: true,
    new_files: false,
    missed_calls: true,
    weekly_summary: false,
  });
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

  // Initialize form with user data
  useEffect(() => {
    if (user) {
      setProfileForm({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
      });
    }
  }, [user]);

  // Handle profile save
  const handleSaveProfile = async () => {
    setIsSavingProfile(true);
    try {
      const response = await authApi.updateProfile(profileForm);
      // Update local user state
      if (response.data) {
        setUser(response.data);
      }
      showToast('success', response.message || 'Το προφίλ αποθηκεύτηκε');
    } catch (error) {
      console.error('Profile save error:', error);
      showToast('error', 'Σφάλμα κατά την αποθήκευση');
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Handle notification settings save (αποθήκευση στον server, ανά χρήστη)
  const handleSaveNotifications = async () => {
    setIsSavingNotifications(true);
    try {
      await apiClient.put('/api/v1/notifications/settings/', notificationSettings);
      showToast('success', 'Οι ρυθμίσεις ειδοποιήσεων αποθηκεύτηκαν');
    } catch (error) {
      console.error('Notification settings save error:', error);
      showToast('error', 'Σφάλμα κατά την αποθήκευση');
    } finally {
      setIsSavingNotifications(false);
    }
  };

  // Load notification settings from server on mount
  useEffect(() => {
    apiClient
      .get('/api/v1/notifications/settings/')
      .then((response) => {
        const { email_reminders, email_overdue, new_files, missed_calls, weekly_summary } =
          response.data;
        setNotificationSettings({ email_reminders, email_overdue, new_files, missed_calls, weekly_summary });
      })
      .catch((error) => console.error('Notification settings load error:', error));
  }, []);

  // GSIS Settings State
  const [gsisConfigured, setGsisConfigured] = useState(false);
  const [gsisAfm, setGsisAfm] = useState('');
  const [gsisUsername, setGsisUsername] = useState('');
  const [gsisPassword, setGsisPassword] = useState('');
  const [gsisLoading, setGsisLoading] = useState(false);
  const [gsisTesting, setGsisTesting] = useState(false);
  const [gsisMessage, setGsisMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showGsisModal, setShowGsisModal] = useState(false);

  // Load GSIS status on mount
  useEffect(() => {
    loadGsisStatus();
  }, []);

  const loadGsisStatus = async () => {
    try {
      const status = await gsisApi.getStatus();
      setGsisConfigured(status.configured);
      if (status.afm) {
        setGsisAfm(status.afm);
      }
      if (status.username) {
        setGsisUsername(status.username);
      }
    } catch (error) {
      console.error('Failed to load GSIS status:', error);
    }
  };

  const handleSaveGsisSettings = async () => {
    // Validate AFM
    if (!gsisAfm.trim() || gsisAfm.length !== 9 || !/^\d+$/.test(gsisAfm)) {
      setGsisMessage({ type: 'error', text: 'Το ΑΦΜ πρέπει να αποτελείται από 9 ψηφία' });
      return;
    }
    if (!gsisUsername.trim()) {
      setGsisMessage({ type: 'error', text: 'Το όνομα χρήστη είναι υποχρεωτικό' });
      return;
    }
    if (!gsisConfigured && !gsisPassword.trim()) {
      setGsisMessage({ type: 'error', text: 'Ο κωδικός είναι υποχρεωτικός' });
      return;
    }

    setGsisLoading(true);
    setGsisMessage(null);

    try {
      const data: { afm: string; username: string; password?: string; is_active: boolean } = {
        afm: gsisAfm,
        username: gsisUsername,
        is_active: true,
      };
      if (gsisPassword.trim()) {
        data.password = gsisPassword;
      }

      await gsisApi.updateSettings(data);
      setGsisMessage({ type: 'success', text: 'Οι ρυθμίσεις αποθηκεύτηκαν!' });
      setGsisPassword('');
      await loadGsisStatus();
      setTimeout(() => setShowGsisModal(false), 1500);
    } catch {
      setGsisMessage({ type: 'error', text: 'Αποτυχία αποθήκευσης ρυθμίσεων' });
    } finally {
      setGsisLoading(false);
    }
  };

  const handleTestGsisConnection = async () => {
    setGsisTesting(true);
    setGsisMessage(null);

    try {
      const result = await gsisApi.testConnection();
      if (result.success) {
        setGsisMessage({ type: 'success', text: result.message });
      } else {
        setGsisMessage({ type: 'error', text: result.message });
      }
    } catch {
      setGsisMessage({ type: 'error', text: 'Αποτυχία δοκιμής σύνδεσης' });
    } finally {
      setGsisTesting(false);
    }
  };

  const tabs = [
    { id: 'profile' as const, label: 'Προφίλ', icon: User },
    { id: 'notifications' as const, label: 'Ειδοποιήσεις', icon: Bell },
    { id: 'security' as const, label: 'Ασφάλεια', icon: Shield },
    { id: 'integrations' as const, label: 'Ενσωματώσεις', icon: Database },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader title="Ρυθμίσεις" subtitle="Διαχείριση λογαριασμού και προτιμήσεων" />

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar Tabs */}
        <div className="lg:w-64 flex-shrink-0">
          <nav className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'bg-brand-50 text-brand-700 border-l-2 border-brand-600'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <tab.icon size={18} />
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-6">Στοιχεία προφίλ</h3>

              {/* Avatar */}
              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-slate-200">
                <div className="w-20 h-20 bg-brand-600 rounded-full flex items-center justify-center">
                  <span className="text-3xl text-white font-bold">
                    {user?.first_name?.charAt(0) || user?.username?.charAt(0) || 'Χ'}
                  </span>
                </div>
                <div>
                  <Button variant="secondary" size="sm">Αλλαγή φωτογραφίας</Button>
                  <p className="text-xs text-slate-500 mt-1">JPG, PNG έως 5MB</p>
                </div>
              </div>

              {/* Form */}
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="settings-onoma" className="block text-sm font-medium text-slate-700 mb-1">Όνομα</label>
                    <input
                      id="settings-onoma"
                      type="text"
                      value={profileForm.first_name}
                      onChange={(e) => setProfileForm({ ...profileForm, first_name: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="settings-eponymo" className="block text-sm font-medium text-slate-700 mb-1">Επώνυμο</label>
                    <input
                      id="settings-eponymo"
                      type="text"
                      value={profileForm.last_name}
                      onChange={(e) => setProfileForm({ ...profileForm, last_name: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="settings-email" className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                  <input
                    id="settings-email"
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  />
                </div>

                <div>
                  <label htmlFor="settings-onoma-christi" className="block text-sm font-medium text-slate-700 mb-1">Όνομα χρήστη</label>
                  <input
                    id="settings-onoma-christi"
                    type="text"
                    defaultValue={user?.username || ''}
                    disabled
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-500"
                  />
                  <p className="text-xs text-slate-500 mt-1">Το όνομα χρήστη δεν μπορεί να αλλάξει</p>
                </div>

                <div className="pt-4">
                  <Button onClick={handleSaveProfile} disabled={isSavingProfile}>
                    {isSavingProfile ? (
                      <>
                        <RefreshCw size={18} className="mr-2 animate-spin" />
                        Αποθήκευση...
                      </>
                    ) : (
                      <>
                        <Save size={18} className="mr-2" />
                        Αποθήκευση αλλαγών
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-6">Ρυθμίσεις ειδοποιήσεων</h3>

              <div className="space-y-4">
                {[
                  { key: 'email_reminders' as const, title: 'Email υπενθυμίσεων', desc: 'Λήψη email για επερχόμενες υποχρεώσεις' },
                  { key: 'email_overdue' as const, title: 'Email για εκπρόθεσμες', desc: 'Ειδοποίηση όταν μια υποχρέωση καθυστερεί' },
                  { key: 'new_files' as const, title: 'Νέα αρχεία', desc: 'Ειδοποίηση όταν προστίθεται νέο αρχείο' },
                  { key: 'missed_calls' as const, title: 'Αναπάντητες κλήσεις', desc: 'Ειδοποίηση για αναπάντητες κλήσεις' },
                  { key: 'weekly_summary' as const, title: 'Εβδομαδιαία σύνοψη', desc: 'Αναφορά προόδου κάθε Δευτέρα' },
                ].map((item) => (
                  <div key={item.key} className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                    <div>
                      <p className="font-medium text-slate-900">{item.title}</p>
                      <p className="text-sm text-slate-500">{item.desc}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={notificationSettings[item.key]}
                        onChange={(e) => setNotificationSettings(prev => ({ ...prev, [item.key]: e.target.checked }))}
                      />
                      <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                    </label>
                  </div>
                ))}
              </div>

              <div className="pt-6">
                <Button onClick={handleSaveNotifications} disabled={isSavingNotifications}>
                  {isSavingNotifications ? (
                    <>
                      <RefreshCw size={18} className="mr-2 animate-spin" />
                      Αποθήκευση...
                    </>
                  ) : (
                    <>
                      <Save size={18} className="mr-2" />
                      Αποθήκευση ρυθμίσεων
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-6">Αλλαγή κωδικού</h3>

                <div className="space-y-4 max-w-md">
                  <div>
                    <label htmlFor="settings-trechon-kodikos" className="block text-sm font-medium text-slate-700 mb-1">Τρέχων κωδικός</label>
                    <input
                      id="settings-trechon-kodikos"
                      type="password"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="settings-neos-kodikos" className="block text-sm font-medium text-slate-700 mb-1">Νέος κωδικός</label>
                    <input
                      id="settings-neos-kodikos"
                      type="password"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="settings-epivevaiosi-neoy-kodikoy" className="block text-sm font-medium text-slate-700 mb-1">Επιβεβαίωση νέου κωδικού</label>
                    <input
                      id="settings-epivevaiosi-neoy-kodikoy"
                      type="password"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                    />
                  </div>
                  <Button>Αλλαγή κωδικού</Button>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Συνδεδεμένες συνεδρίες</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-success-100 rounded-lg flex items-center justify-center">
                        <Globe size={18} className="text-success-600" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">Τρέχουσα συνεδρία</p>
                        <p className="text-xs text-slate-500">Chrome · Linux · Athens, GR</p>
                      </div>
                    </div>
                    <span className="px-2 py-1 text-xs bg-success-100 text-success-700 rounded">Ενεργή</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-6">
              {/* Quick Links */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Obligation Settings */}
                <Link
                  to="/settings/obligations"
                  className="block bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-brand-300 hover:shadow-md transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-brand-100 rounded-lg flex items-center justify-center">
                        <FileText size={24} className="text-brand-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-900">Υποχρεώσεις</h3>
                        <p className="text-sm text-slate-500">Τύποι, προφίλ, ομάδες</p>
                      </div>
                    </div>
                    <ChevronRight className="text-slate-400" size={20} />
                  </div>
                </Link>

                {/* User Management - Only for staff/superuser */}
                {user?.is_staff && (
                  <Link
                    to="/settings/users"
                    className="block bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-purple-300 hover:shadow-md transition-all cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                          <Users size={24} className="text-purple-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-slate-900">Χρήστες</h3>
                          <p className="text-sm text-slate-500">Διαχείριση λογαριασμών</p>
                        </div>
                      </div>
                      <ChevronRight className="text-slate-400" size={20} />
                    </div>
                  </Link>
                )}

                {/* Backup - Only for staff/superuser */}
                {user?.is_staff && (
                  <Link
                    to="/settings/backup"
                    className="block bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-success-100 hover:shadow-md transition-all cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-success-100 rounded-lg flex items-center justify-center">
                          <HardDrive size={24} className="text-success-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-slate-900">Backup & Restore</h3>
                          <p className="text-sm text-slate-500">Αντίγραφα ασφαλείας</p>
                        </div>
                      </div>
                      <ChevronRight className="text-slate-400" size={20} />
                    </div>
                  </Link>
                )}

                {/* Filing System Settings - Only for staff/superuser */}
                {user?.is_staff && (
                  <Link
                    to="/settings/filing"
                    className="block bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-cyan-300 hover:shadow-md transition-all cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-cyan-100 rounded-lg flex items-center justify-center">
                          <FolderTree size={24} className="text-cyan-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-slate-900">Αρχειοθέτηση</h3>
                          <p className="text-sm text-slate-500">Δομή φακέλων & ρυθμίσεις</p>
                        </div>
                      </div>
                      <ChevronRight className="text-slate-400" size={20} />
                    </div>
                  </Link>
                )}

                {/* Email Settings */}
                <Link
                  to="/settings/email"
                  className="block bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:border-warning-100 hover:shadow-md transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-warning-100 rounded-lg flex items-center justify-center">
                        <Mail size={24} className="text-warning-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-900">Ρυθμίσεις Email</h3>
                        <p className="text-sm text-slate-500">SMTP server, αποστολέας</p>
                      </div>
                    </div>
                    <ChevronRight className="text-slate-400" size={20} />
                  </div>
                </Link>
              </div>

              {/* GSIS Integration - Λήψη στοιχείων με ΑΦΜ */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-6">ΑΑΔΕ - Λήψη Στοιχείων</h3>

                <div className="flex items-center justify-between p-4 border border-slate-200 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${gsisConfigured ? 'bg-success-100' : 'bg-slate-100'}`}>
                      <Database size={24} className={gsisConfigured ? 'text-success-600' : 'text-slate-600'} />
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">Λήψη Στοιχείων με ΑΦΜ</p>
                      <p className="text-sm text-slate-500">
                        {gsisConfigured
                          ? `Ρυθμισμένο (${gsisUsername})`
                          : 'Ειδικοί κωδικοί λήψης στοιχείων ΑΑΔΕ'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {gsisConfigured ? (
                      <>
                        <span className="px-2 py-1 text-xs bg-success-100 text-success-700 rounded">Ρυθμισμένο</span>
                        <Button variant="secondary" size="sm" onClick={() => setShowGsisModal(true)}>Ρυθμίσεις</Button>
                      </>
                    ) : (
                      <Button size="sm" onClick={() => setShowGsisModal(true)}>Ρύθμιση</Button>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-lg font-semibold text-slate-900 mb-6">Άλλες Ενσωματώσεις</h3>

                <div className="space-y-4">
                {[
                  {
                    name: 'Fritz!Box VoIP',
                    desc: 'Σύνδεση με τηλεφωνικό κέντρο Fritz!Box',
                    icon: Phone,
                    status: 'connected'
                  },
                  {
                    name: 'Zadarma',
                    desc: 'Cloud PBX και click-to-call',
                    icon: Phone,
                    status: 'disconnected'
                  },
                  {
                    name: 'SMTP Email',
                    desc: 'Αποστολή email μέσω SMTP server',
                    icon: Mail,
                    status: 'connected'
                  },
                  {
                    name: 'MyData ΑΑΔΕ',
                    desc: 'Σύνδεση με την πλατφόρμα myDATA (Συνοπτικό Βιβλίο)',
                    icon: Database,
                    status: 'disconnected'
                  },
                ].map((item, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border border-slate-200 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                        <item.icon size={24} className="text-slate-600" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{item.name}</p>
                        <p className="text-sm text-slate-500">{item.desc}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {item.status === 'connected' ? (
                        <>
                          <span className="px-2 py-1 text-xs bg-success-100 text-success-700 rounded">Συνδεδεμένο</span>
                          <Button variant="secondary" size="sm">Ρυθμίσεις</Button>
                        </>
                      ) : (
                        <Button size="sm" disabled>Σύντομα</Button>
                      )}
                    </div>
                  </div>
                ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* GSIS Settings Modal */}
      {showGsisModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900">
                Ρυθμίσεις GSIS - Λήψη Στοιχείων
              </h3>
              <button
                onClick={() => {
                  setShowGsisModal(false);
                  setGsisMessage(null);
                }}
                className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-sm text-slate-600">
                Εισάγετε τους "Ειδικούς Κωδικούς Λήψης Στοιχείων" που έχετε λάβει από την ΑΑΔΕ.
              </p>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  ΑΦΜ Λογιστή *
                </label>
                <input
                  type="text"
                  value={gsisAfm}
                  onChange={(e) => setGsisAfm(e.target.value.replace(/\D/g, '').slice(0, 9))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  placeholder="123456789"
                  maxLength={9}
                />
                <p className="text-xs text-slate-500 mt-1">
                  Το ΑΦΜ σας (9 ψηφία) - χρησιμοποιείται ως afm_called_by
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Όνομα Χρήστη *
                </label>
                <input
                  type="text"
                  value={gsisUsername}
                  onChange={(e) => setGsisUsername(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  placeholder="Εισάγετε username"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Κωδικός {!gsisConfigured && '*'}
                </label>
                <input
                  type="password"
                  value={gsisPassword}
                  onChange={(e) => setGsisPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  placeholder={gsisConfigured ? 'Αφήστε κενό για να διατηρηθεί ο υπάρχων' : 'Εισάγετε password'}
                />
                {gsisConfigured && (
                  <p className="text-xs text-slate-500 mt-1">
                    Αφήστε κενό αν δεν θέλετε να αλλάξετε τον κωδικό
                  </p>
                )}
              </div>

              {gsisMessage && (
                <div className={`p-3 rounded-lg flex items-center gap-2 ${
                  gsisMessage.type === 'success'
                    ? 'bg-success-50 text-success-700'
                    : 'bg-danger-50 text-danger-700'
                }`}>
                  {gsisMessage.type === 'success' ? <Check size={18} /> : <X size={18} />}
                  {gsisMessage.text}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-slate-50 rounded-b-lg">
              <Button
                variant="secondary"
                onClick={handleTestGsisConnection}
                disabled={!gsisConfigured || gsisTesting}
              >
                {gsisTesting ? (
                  <>
                    <Loader2 size={18} className="animate-spin mr-2" />
                    Δοκιμή...
                  </>
                ) : (
                  'Δοκιμή Σύνδεσης'
                )}
              </Button>

              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowGsisModal(false);
                    setGsisMessage(null);
                  }}
                >
                  Ακύρωση
                </Button>
                <Button
                  onClick={handleSaveGsisSettings}
                  disabled={gsisLoading}
                >
                  {gsisLoading ? (
                    <>
                      <Loader2 size={18} className="animate-spin mr-2" />
                      Αποθήκευση...
                    </>
                  ) : (
                    <>
                      <Save size={18} className="mr-2" />
                      Αποθήκευση
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
