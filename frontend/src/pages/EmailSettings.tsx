/**
 * EmailSettings.tsx
 * Page for managing email/SMTP settings
 */

import { useState, useEffect } from 'react';
import {
  Mail,
  Server,
  Shield,
  User,
  Building2,
  RefreshCw,
  Check,
  X,
  AlertCircle,
  Send,
  Eye,
  EyeOff,
  TestTube,
  Save,
} from 'lucide-react';
import { Button } from '../components';
import {
  useEmailSettings,
  useUpdateEmailSettings,
  useTestEmailConnection,
  useSendTestEmail,
  type EmailSettingsUpdateData,
} from '../hooks/useEmail';

// Security options
const SECURITY_OPTIONS = [
  { value: 'tls', label: 'TLS (Port 587)', description: 'Συνιστάται για Gmail και τους περισσότερους providers' },
  { value: 'ssl', label: 'SSL (Port 465)', description: 'Παλαιότερο πρότυπο, ακόμα υποστηρίζεται' },
  { value: 'none', label: 'Κανένα (Port 25)', description: 'Μόνο για τοπικούς servers' },
];

// Common SMTP presets
const SMTP_PRESETS = [
  { name: 'Gmail', host: 'smtp.gmail.com', port: 587, security: 'tls' as const },
  { name: 'Outlook', host: 'smtp.office365.com', port: 587, security: 'tls' as const },
  { name: 'Yahoo', host: 'smtp.mail.yahoo.com', port: 465, security: 'ssl' as const },
  { name: 'Zoho', host: 'smtp.zoho.eu', port: 587, security: 'tls' as const },
];

export default function EmailSettings() {
  const { data: settings, isLoading, isError, error, refetch } = useEmailSettings();
  const updateMutation = useUpdateEmailSettings();
  const testConnectionMutation = useTestEmailConnection();
  const sendTestMutation = useSendTestEmail();

  const [formData, setFormData] = useState<EmailSettingsUpdateData>({});
  const [showPassword, setShowPassword] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize form data when settings load
  useEffect(() => {
    if (settings) {
      setFormData({
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_username: settings.smtp_username,
        smtp_security: settings.smtp_security,
        from_email: settings.from_email,
        from_name: settings.from_name,
        reply_to: settings.reply_to,
        company_name: settings.company_name,
        company_phone: settings.company_phone,
        company_website: settings.company_website,
        accountant_name: settings.accountant_name,
        accountant_title: settings.accountant_title,
        email_signature: settings.email_signature,
        rate_limit: settings.rate_limit,
        burst_limit: settings.burst_limit,
        is_active: settings.is_active,
      });
    }
  }, [settings]);

  // Handle form changes
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox'
        ? (e.target as HTMLInputElement).checked
        : type === 'number'
          ? Number(value)
          : value,
    }));
    setHasChanges(true);
    setSuccessMessage(null);
    setErrorMessage(null);
  };

  // Apply SMTP preset
  const applyPreset = (preset: typeof SMTP_PRESETS[0]) => {
    setFormData((prev) => ({
      ...prev,
      smtp_host: preset.host,
      smtp_port: preset.port,
      smtp_security: preset.security,
    }));
    setHasChanges(true);
  };

  // Save settings
  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync(formData);
      setSuccessMessage('Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς!');
      setHasChanges(false);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Σφάλμα αποθήκευσης');
    }
  };

  // Test SMTP connection
  const handleTestConnection = async () => {
    try {
      const result = await testConnectionMutation.mutateAsync(formData);
      if (result.success) {
        setSuccessMessage(result.message);
      } else {
        setErrorMessage(result.message);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Σφάλμα σύνδεσης');
    }
  };

  // Send test email
  const handleSendTestEmail = async () => {
    if (!testEmail) {
      setErrorMessage('Εισάγετε email παραλήπτη');
      return;
    }
    try {
      const result = await sendTestMutation.mutateAsync(testEmail);
      if (result.success) {
        setSuccessMessage(result.message);
      } else {
        setErrorMessage(result.message);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Σφάλμα αποστολής');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
        <span className="ml-3 text-gray-600">Φόρτωση ρυθμίσεων...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-800">Σφάλμα φόρτωσης</h3>
            <p className="text-red-600">{error instanceof Error ? error.message : 'Άγνωστο σφάλμα'}</p>
          </div>
          <Button variant="secondary" onClick={() => refetch()} className="ml-auto">
            <RefreshCw className="w-4 h-4 mr-2" />
            Επανάληψη
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-brand-100 rounded-lg">
            <Mail className="w-6 h-6 text-brand-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Ρυθμίσεις Email</h1>
            <p className="text-sm text-gray-500">Διαμόρφωση SMTP server και στοιχείων αποστολέα</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {settings?.last_test_success !== null && (
            <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm ${
              settings?.last_test_success
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}>
              {settings?.last_test_success ? (
                <Check className="w-4 h-4" />
              ) : (
                <X className="w-4 h-4" />
              )}
              {settings?.last_test_success ? 'Επιτυχής σύνδεση' : 'Αποτυχία σύνδεσης'}
            </div>
          )}
          <Button
            onClick={handleSave}
            disabled={!hasChanges || updateMutation.isPending}
            isLoading={updateMutation.isPending}
          >
            <Save className="w-4 h-4 mr-2" />
            Αποθήκευση
          </Button>
        </div>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-2">
          <Check className="w-5 h-5 text-green-500" />
          <span className="text-green-700">{successMessage}</span>
          <button onClick={() => setSuccessMessage(null)} className="ml-auto">
            <X className="w-4 h-4 text-green-500" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700">{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="ml-auto">
            <X className="w-4 h-4 text-red-500" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SMTP Settings Section */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Server className="w-5 h-5 text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Ρυθμίσεις SMTP</h2>
          </div>

          {/* Quick Presets */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Γρήγορη Ρύθμιση
            </label>
            <div className="flex flex-wrap gap-2">
              {SMTP_PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  onClick={() => applyPreset(preset)}
                  className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  {preset.name}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            {/* SMTP Host */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                SMTP Server
              </label>
              <input
                type="text"
                name="smtp_host"
                value={formData.smtp_host || ''}
                onChange={handleChange}
                placeholder="smtp.gmail.com"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            {/* SMTP Port & Security */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Port
                </label>
                <input
                  type="number"
                  name="smtp_port"
                  value={formData.smtp_port || 587}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ασφάλεια
                </label>
                <select
                  name="smtp_security"
                  value={formData.smtp_security || 'tls'}
                  onChange={handleChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                >
                  {SECURITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* SMTP Username */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Όνομα Χρήστη (Email)
              </label>
              <input
                type="email"
                name="smtp_username"
                value={formData.smtp_username || ''}
                onChange={handleChange}
                placeholder="your-email@gmail.com"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            {/* SMTP Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-2">
                Κωδικός (App Password)
                {settings?.has_password && (
                  <span className="inline-flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                    <Check className="w-3 h-3" />
                    Αποθηκευμένος
                  </span>
                )}
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="smtp_password"
                  value={formData.smtp_password || ''}
                  onChange={handleChange}
                  placeholder={settings?.has_password ? 'Νέος κωδικός (προαιρετικά)' : 'Εισάγετε κωδικό'}
                  className={`w-full px-3 py-2 pr-10 border rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
                    settings?.has_password && !formData.smtp_password
                      ? 'border-green-300 bg-green-50'
                      : 'border-gray-300'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {settings?.has_password && !formData.smtp_password ? (
                <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  Ο κωδικός είναι αποθηκευμένος με κρυπτογράφηση. Αφήστε κενό για να τον διατηρήσετε.
                </p>
              ) : !settings?.has_password && !formData.smtp_password ? (
                <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  Δεν έχει οριστεί κωδικός. Απαιτείται για αποστολή email.
                </p>
              ) : null}
            </div>

            {/* Gmail Help */}
            <div className="bg-brand-50 border border-brand-200 rounded-lg p-4">
              <h4 className="font-medium text-brand-800 mb-2 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Για Gmail / Google Workspace
              </h4>
              <ul className="text-sm text-brand-700 space-y-1 list-disc list-inside">
                <li>Ενεργοποιήστε 2-Factor Authentication</li>
                <li>Δημιουργήστε App Password από τις ρυθμίσεις Google</li>
                <li>Χρησιμοποιήστε το App Password αντί για τον κανονικό κωδικό</li>
              </ul>
            </div>

            {/* Test Connection Button */}
            <div className="pt-4 border-t border-gray-200">
              <Button
                variant="secondary"
                onClick={handleTestConnection}
                isLoading={testConnectionMutation.isPending}
                className="w-full"
              >
                <TestTube className="w-4 h-4 mr-2" />
                Δοκιμή Σύνδεσης SMTP
              </Button>
            </div>
          </div>
        </div>

        {/* Sender Info Section */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-6">
              <User className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">Στοιχεία Αποστολέα</h2>
            </div>

            <div className="space-y-4">
              {/* From Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Αποστολέα *
                </label>
                <input
                  type="email"
                  name="from_email"
                  value={formData.from_email || ''}
                  onChange={handleChange}
                  placeholder="info@example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>

              {/* From Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Όνομα Αποστολέα
                </label>
                <input
                  type="text"
                  name="from_name"
                  value={formData.from_name || ''}
                  onChange={handleChange}
                  placeholder="Λογιστικό Γραφείο Παπαδόπουλος"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>

              {/* Reply-To */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reply-To Email
                </label>
                <input
                  type="email"
                  name="reply_to"
                  value={formData.reply_to || ''}
                  onChange={handleChange}
                  placeholder="Αν διαφέρει από το email αποστολέα"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Company Info Section */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-6">
              <Building2 className="w-5 h-5 text-gray-600" />
              <h2 className="text-lg font-semibold text-gray-900">Στοιχεία Εταιρείας</h2>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Όνομα Εταιρείας
                  </label>
                  <input
                    type="text"
                    name="company_name"
                    value={formData.company_name || ''}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Τηλέφωνο
                  </label>
                  <input
                    type="text"
                    name="company_phone"
                    value={formData.company_phone || ''}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Website
                </label>
                <input
                  type="url"
                  name="company_website"
                  value={formData.company_website || ''}
                  onChange={handleChange}
                  placeholder="https://www.example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Όνομα Λογιστή
                  </label>
                  <input
                    type="text"
                    name="accountant_name"
                    value={formData.accountant_name || ''}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Τίτλος
                  </label>
                  <input
                    type="text"
                    name="accountant_title"
                    value={formData.accountant_title || ''}
                    onChange={handleChange}
                    placeholder="Λογιστής Α' Τάξης"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Email Signature Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Υπογραφή Email</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Signature Editor */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              HTML Κώδικας
            </label>
            <textarea
              name="email_signature"
              value={formData.email_signature || ''}
              onChange={handleChange}
              rows={10}
              placeholder="HTML υπογραφή που προστίθεται στα emails..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent font-mono text-sm"
            />
            <p className="text-xs text-gray-500 mt-2">
              Μπορείτε να χρησιμοποιήσετε HTML για μορφοποίηση. Η υπογραφή προστίθεται αυτόματα στο τέλος κάθε email.
            </p>
          </div>

          {/* Signature Preview */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Προεπισκόπηση
            </label>
            <div className="border border-gray-300 rounded-md p-4 bg-gray-50 min-h-[200px]">
              {formData.email_signature ? (
                <div
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: formData.email_signature }}
                />
              ) : (
                <p className="text-gray-400 text-sm italic">
                  Η προεπισκόπηση θα εμφανιστεί εδώ όταν εισάγετε HTML κώδικα...
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Signature Template Suggestions */}
        <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <h4 className="font-medium text-amber-800 mb-2">Παράδειγμα υπογραφής:</h4>
          <pre className="text-xs text-amber-700 overflow-x-auto whitespace-pre-wrap">{`<div style="font-family: Arial, sans-serif; color: #333;">
  <p style="margin: 0;">Με εκτίμηση,</p>
  <p style="margin: 5px 0 0 0; font-weight: bold;">${formData.accountant_name || 'Όνομα Λογιστή'}</p>
  <p style="margin: 0; font-size: 14px; color: #666;">${formData.accountant_title || 'Λογιστής Α\' Τάξης'}</p>
  <p style="margin: 10px 0 0 0; font-size: 14px;">
    <strong>${formData.company_name || 'Όνομα Εταιρείας'}</strong><br/>
    Τηλ: ${formData.company_phone || '210-XXXXXXX'}<br/>
    ${formData.company_website || 'www.example.com'}
  </p>
</div>`}</pre>
        </div>
      </div>

      {/* Test Email Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Δοκιμαστικό Email</h3>
        <p className="text-sm text-gray-600 mb-4">
          Στείλτε ένα δοκιμαστικό email για να επιβεβαιώσετε ότι οι ρυθμίσεις λειτουργούν σωστά.
        </p>
        <div className="flex gap-2">
          <input
            type="email"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
            placeholder="test@example.com"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
          <Button
            onClick={handleSendTestEmail}
            isLoading={sendTestMutation.isPending}
            disabled={!formData.is_active}
          >
            <Send className="w-4 h-4 mr-2" />
            Αποστολή
          </Button>
        </div>
        {!formData.is_active && (
          <p className="text-sm text-amber-600 mt-2">
            Ενεργοποιήστε τις ρυθμίσεις email για να στείλετε δοκιμαστικό
          </p>
        )}
      </div>

      {/* Advanced Settings */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Προχωρημένες Ρυθμίσεις</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Rate Limit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rate Limit (emails/sec)
            </label>
            <input
              type="number"
              name="rate_limit"
              value={formData.rate_limit || 2}
              onChange={handleChange}
              step="0.5"
              min="0.5"
              max="10"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              Μέγιστα emails ανά δευτερόλεπτο
            </p>
          </div>

          {/* Burst Limit */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Burst Limit
            </label>
            <input
              type="number"
              name="burst_limit"
              value={formData.burst_limit || 5}
              onChange={handleChange}
              min="1"
              max="50"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              Μέγιστα emails σε burst
            </p>
          </div>

          {/* Is Active */}
          <div className="flex items-center">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active ?? true}
                onChange={handleChange}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
              <span className="ml-3 text-sm font-medium text-gray-700">
                {formData.is_active ? 'Ενεργό' : 'Απενεργοποιημένο'}
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Last Test Info */}
      {settings?.last_test_at && (
        <div className={`rounded-lg border p-4 ${
          settings.last_test_success
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <h4 className={`font-medium mb-2 ${
            settings.last_test_success ? 'text-green-800' : 'text-red-800'
          }`}>
            Τελευταίο Test: {new Date(settings.last_test_at).toLocaleString('el-GR')}
          </h4>
          {settings.last_test_error && (
            <p className="text-sm text-red-700">{settings.last_test_error}</p>
          )}
        </div>
      )}
    </div>
  );
}
