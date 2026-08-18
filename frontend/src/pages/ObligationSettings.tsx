import { useState, useEffect } from 'react';
import {
  Settings,
  List,
  Layers,
  GitBranch,
  Plus,
  Pencil,
  Trash2,
  X,
  Search,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { Button } from '../components';
import {
  useObligationTypesList,
  useCreateObligationType,
  useUpdateObligationType,
  useDeleteObligationType,
  useObligationProfilesList,
  useCreateObligationProfile,
  useUpdateObligationProfile,
  useDeleteObligationProfile,
  useObligationGroupsList,
  useCreateObligationGroup,
  useUpdateObligationGroup,
  useDeleteObligationGroup,
} from '../hooks/useObligationSettings';
import type {
  ObligationTypeFull,
  ObligationTypeFormData,
  ObligationProfileFull,
  ObligationProfileFormData,
  ObligationGroupFull,
  ObligationGroupFormData,
} from '../types';
import {
  FREQUENCY_LABELS,
  DEADLINE_TYPE_LABELS,
  FREQUENCY_OPTIONS,
  DEADLINE_TYPE_OPTIONS,
} from '../types';

type SettingsTab = 'types' | 'profiles' | 'groups';

// ============================================
// OBLIGATION TYPE MODAL
// ============================================

interface TypeModalProps {
  isOpen: boolean;
  onClose: () => void;
  type?: ObligationTypeFull | null;
  profiles: ObligationProfileFull[];
  groups: ObligationGroupFull[];
}

function ObligationTypeModal({ isOpen, onClose, type, profiles, groups }: TypeModalProps) {
  const isEdit = !!type;
  const createMutation = useCreateObligationType();
  const updateMutation = useUpdateObligationType();

  const [formData, setFormData] = useState<ObligationTypeFormData>({
    code: type?.code || '',
    name: type?.name || '',
    description: type?.description || '',
    frequency: type?.frequency || 'monthly',
    deadline_type: type?.deadline_type || 'last_day',
    deadline_day: type?.deadline_day || null,
    applicable_months: type?.applicable_months || '',
    exclusion_group: type?.exclusion_group || null,
    profiles: type?.profiles || [],  // ManyToMany - array
    priority: type?.priority || 0,
    is_active: type?.is_active ?? true,
  });

  const [error, setError] = useState<string | null>(null);

  const [previousType, setPreviousType] = useState(type);
  if (previousType !== type) {
    setPreviousType(type);
    setFormData({
      code: type?.code || '',
      name: type?.name || '',
      description: type?.description || '',
      frequency: type?.frequency || 'monthly',
      deadline_type: type?.deadline_type || 'last_day',
      deadline_day: type?.deadline_day || null,
      applicable_months: type?.applicable_months || '',
      exclusion_group: type?.exclusion_group || null,
      profiles: type?.profiles || [],  // ManyToMany - array
      priority: type?.priority || 0,
      is_active: type?.is_active ?? true,
    });
    setError(null);
  }

  // Toggle profile in selection
  const toggleProfile = (profileId: number) => {
    const current = formData.profiles || [];
    if (current.includes(profileId)) {
      setFormData({ ...formData, profiles: current.filter(id => id !== profileId) });
    } else {
      setFormData({ ...formData, profiles: [...current, profileId] });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (isEdit && type) {
        await updateMutation.mutateAsync({ id: type.id, data: formData });
      } else {
        await createMutation.mutateAsync(formData);
      }
      onClose();
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { code?: string[]; name?: string[]; error?: string } } };
      const errorData = errorObj.response?.data;
      if (errorData?.code) {
        setError(errorData.code[0]);
      } else if (errorData?.name) {
        setError(errorData.name[0]);
      } else if (errorData?.error) {
        setError(errorData.error);
      } else {
        setError('Σφάλμα κατά την αποθήκευση.');
      }
    }
  };

  if (!isOpen) return null;

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            {isEdit ? 'Επεξεργασία Τύπου' : 'Νέος Τύπος Υποχρέωσης'}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-danger-50 text-danger-700 rounded-lg text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="obligation-settings-f1" className="block text-sm font-medium text-slate-700 mb-1">
                Κωδικός <span className="text-danger-600">*</span>
              </label>
              <input id="obligation-settings-f1"
                type="text"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                placeholder="π.χ. ΦΠΑ"
                required
              />
            </div>
            <div>
              <label htmlFor="obligation-settings-f2" className="block text-sm font-medium text-slate-700 mb-1">
                Όνομα <span className="text-danger-600">*</span>
              </label>
              <input id="obligation-settings-f2"
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                placeholder="Φόρος Προστιθέμενης Αξίας"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="oblsettings-perigrafi-3" className="block text-sm font-medium text-slate-700 mb-1">Περιγραφή</label>
            <textarea
              id="oblsettings-perigrafi-3"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="oblsettings-sychnotita" className="block text-sm font-medium text-slate-700 mb-1">Συχνότητα</label>
              <select
                id="oblsettings-sychnotita"
                value={formData.frequency}
                onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              >
                {FREQUENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="oblsettings-typos-prothesmias" className="block text-sm font-medium text-slate-700 mb-1">Τύπος Προθεσμίας</label>
              <select
                id="oblsettings-typos-prothesmias"
                value={formData.deadline_type}
                onChange={(e) => setFormData({ ...formData, deadline_type: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              >
                {DEADLINE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {formData.deadline_type === 'specific_day' && (
            <div>
              <label htmlFor="oblsettings-imera-prothesmias" className="block text-sm font-medium text-slate-700 mb-1">Ημέρα Προθεσμίας</label>
              <input
                id="oblsettings-imera-prothesmias"
                type="number"
                min={1}
                max={31}
                value={formData.deadline_day || ''}
                onChange={(e) =>
                  setFormData({ ...formData, deadline_day: e.target.value ? parseInt(e.target.value) : null })
                }
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                placeholder="π.χ. 20"
              />
            </div>
          )}

          {(formData.frequency === 'quarterly' || formData.frequency === 'annual') && (
            <div>
              <label htmlFor="obligation-settings-f3" className="block text-sm font-medium text-slate-700 mb-1">
                Μήνες Εφαρμογής
                <span className="text-slate-400 text-xs ml-1">(π.χ. 3,6,9,12)</span>
              </label>
              <input id="obligation-settings-f3"
                type="text"
                value={formData.applicable_months || ''}
                onChange={(e) => setFormData({ ...formData, applicable_months: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                placeholder="3,6,9,12"
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Προφίλ
                <span className="ml-2 text-xs text-slate-500">
                  ({(formData.profiles || []).length} επιλεγμένα)
                </span>
              </label>
              <div className="border border-slate-200 rounded-lg max-h-32 overflow-y-auto">
                {profiles.length === 0 ? (
                  <p className="p-2 text-slate-500 text-sm">Δεν υπάρχουν προφίλ.</p>
                ) : (
                  profiles.map((p) => (
                    <label
                      key={p.id}
                      className="flex items-center gap-2 p-2 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={(formData.profiles || []).includes(p.id)}
                        onChange={() => toggleProfile(p.id)}
                        className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                      />
                      <span className="text-sm text-slate-700">{p.name}</span>
                    </label>
                  ))
                )}
              </div>
            </div>
            <div>
              <label htmlFor="oblsettings-omada-alliloapokleismoy" className="block text-sm font-medium text-slate-700 mb-1">Ομάδα Αλληλοαποκλεισμού</label>
              <select
                id="oblsettings-omada-alliloapokleismoy"
                value={formData.exclusion_group || ''}
                onChange={(e) =>
                  setFormData({ ...formData, exclusion_group: e.target.value ? parseInt(e.target.value) : null })
                }
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              >
                <option value="">-- Χωρίς ομάδα --</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="oblsettings-proteraiotita" className="block text-sm font-medium text-slate-700 mb-1">Προτεραιότητα</label>
              <input
                id="oblsettings-proteraiotita"
                type="number"
                value={formData.priority || 0}
                onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              />
            </div>
            <div className="flex items-center pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                />
                <span className="text-sm text-slate-700">Ενεργό</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
            <Button type="button" variant="secondary" onClick={onClose}>
              Ακύρωση
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Αποθήκευση...' : isEdit ? 'Ενημέρωση' : 'Δημιουργία'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// OBLIGATION PROFILE MODAL
// ============================================

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile?: ObligationProfileFull | null;
  allTypes: ObligationTypeFull[];
}

function ObligationProfileModal({ isOpen, onClose, profile, allTypes }: ProfileModalProps) {
  const isEdit = !!profile;
  const createMutation = useCreateObligationProfile();
  const updateMutation = useUpdateObligationProfile();

  const [formData, setFormData] = useState<ObligationProfileFormData>({
    name: profile?.name || '',
    description: profile?.description || '',
  });

  const [selectedTypeIds, setSelectedTypeIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSavingTypes, setIsSavingTypes] = useState(false);

  // Reset form data when profile changes
  useEffect(() => {
    setFormData({
      name: profile?.name || '',
      description: profile?.description || '',
    });
    // Set selected types based on which types have this profile assigned
    if (profile) {
      const linkedTypeIds = profile.obligation_types?.map(t => t.id) || [];
      setSelectedTypeIds(linkedTypeIds);
    } else {
      setSelectedTypeIds([]);
    }
    setError(null);
  }, [profile]);

  const toggleType = (typeId: number) => {
    if (selectedTypeIds.includes(typeId)) {
      setSelectedTypeIds(selectedTypeIds.filter(id => id !== typeId));
    } else {
      setSelectedTypeIds([...selectedTypeIds, typeId]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      let profileId: number;

      if (isEdit && profile) {
        await updateMutation.mutateAsync({ id: profile.id, data: formData });
        profileId = profile.id;
      } else {
        const result = await createMutation.mutateAsync(formData);
        profileId = result.id;
      }

      // Update type assignments
      if (isEdit && profile) {
        setIsSavingTypes(true);
        const { default: apiClient } = await import('../api/client');

        // Get current types assigned to this profile
        const currentTypeIds = profile.obligation_types?.map(t => t.id) || [];

        // Types to add (in selectedTypeIds but not in currentTypeIds)
        const toAdd = selectedTypeIds.filter(id => !currentTypeIds.includes(id));
        // Types to remove (in currentTypeIds but not in selectedTypeIds)
        const toRemove = currentTypeIds.filter(id => !selectedTypeIds.includes(id));

        if (toAdd.length > 0) {
          await apiClient.post(`api/v1/settings/obligation-profiles/${profileId}/add_types/`, {
            obligation_type_ids: toAdd
          });
        }
        if (toRemove.length > 0) {
          await apiClient.post(`api/v1/settings/obligation-profiles/${profileId}/remove_types/`, {
            obligation_type_ids: toRemove
          });
        }
        setIsSavingTypes(false);
      }

      onClose();
    } catch (err: unknown) {
      setIsSavingTypes(false);
      const errorObj = err as { response?: { data?: { name?: string[]; error?: string } } };
      const errorData = errorObj.response?.data;
      if (errorData?.name) {
        setError(errorData.name[0]);
      } else if (errorData?.error) {
        setError(errorData.error);
      } else {
        setError('Σφάλμα κατά την αποθήκευση.');
      }
    }
  };

  if (!isOpen) return null;

  const isPending = createMutation.isPending || updateMutation.isPending || isSavingTypes;
  const activeTypes = allTypes.filter(t => t.is_active);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            {isEdit ? 'Επεξεργασία Προφίλ' : 'Νέο Προφίλ Υποχρεώσεων'}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-danger-50 text-danger-700 rounded-lg text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div>
            <label htmlFor="obligation-settings-f4" className="block text-sm font-medium text-slate-700 mb-1">
              Όνομα <span className="text-danger-600">*</span>
            </label>
            <input id="obligation-settings-f4"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              placeholder="π.χ. Μισθοδοσία"
              required
            />
          </div>

          <div>
            <label htmlFor="oblsettings-perigrafi-2" className="block text-sm font-medium text-slate-700 mb-1">Περιγραφή</label>
            <textarea
              id="oblsettings-perigrafi-2"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              placeholder="Περιγραφή του προφίλ..."
            />
          </div>

          {/* Obligation Types Checklist */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Τύποι Υποχρεώσεων στο προφίλ
              <span className="ml-2 text-xs text-slate-500">
                ({selectedTypeIds.length} επιλεγμένοι)
              </span>
            </label>
            <div className="border border-slate-200 rounded-lg max-h-48 overflow-y-auto">
              {activeTypes.length === 0 ? (
                <p className="p-3 text-slate-500 text-sm">Δεν υπάρχουν τύποι υποχρεώσεων.</p>
              ) : (
                activeTypes.map((type) => (
                  <label
                    key={type.id}
                    className="flex items-center gap-3 p-2 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-0"
                  >
                    <input
                      type="checkbox"
                      checked={selectedTypeIds.includes(type.id)}
                      onChange={() => toggleType(type.id)}
                      className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                    />
                    <span className="text-sm text-slate-700">
                      <span className="font-medium text-brand-600">{type.code}</span>
                      {' - '}
                      {type.name}
                    </span>
                  </label>
                ))
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Επιλέξτε τους τύπους υποχρεώσεων που θα ανήκουν σε αυτό το προφίλ.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
            <Button type="button" variant="secondary" onClick={onClose}>
              Ακύρωση
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Αποθήκευση...' : isEdit ? 'Ενημέρωση' : 'Δημιουργία'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// OBLIGATION GROUP MODAL
// ============================================

interface GroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  group?: ObligationGroupFull | null;
  allTypes: ObligationTypeFull[];
}

function ObligationGroupModal({ isOpen, onClose, group, allTypes }: GroupModalProps) {
  const isEdit = !!group;
  const createMutation = useCreateObligationGroup();
  const updateMutation = useUpdateObligationGroup();

  const [formData, setFormData] = useState<ObligationGroupFormData>({
    name: group?.name || '',
    description: group?.description || '',
    obligation_types: group?.obligation_types || [],
  });

  const [error, setError] = useState<string | null>(null);

  const [previousGroup, setPreviousGroup] = useState(group);
  if (previousGroup !== group) {
    setPreviousGroup(group);
    setFormData({
      name: group?.name || '',
      description: group?.description || '',
      obligation_types: group?.obligation_types || [],
    });
    setError(null);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (isEdit && group) {
        await updateMutation.mutateAsync({ id: group.id, data: formData });
      } else {
        await createMutation.mutateAsync(formData);
      }
      onClose();
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { name?: string[]; error?: string } } };
      const errorData = errorObj.response?.data;
      if (errorData?.name) {
        setError(errorData.name[0]);
      } else if (errorData?.error) {
        setError(errorData.error);
      } else {
        setError('Σφάλμα κατά την αποθήκευση.');
      }
    }
  };

  const toggleType = (typeId: number) => {
    const current = formData.obligation_types || [];
    if (current.includes(typeId)) {
      setFormData({ ...formData, obligation_types: current.filter((id) => id !== typeId) });
    } else {
      setFormData({ ...formData, obligation_types: [...current, typeId] });
    }
  };

  if (!isOpen) return null;

  const isPending = createMutation.isPending || updateMutation.isPending;
  const activeTypes = allTypes.filter((t) => t.is_active);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            {isEdit ? 'Επεξεργασία Ομάδας' : 'Νέα Ομάδα Αλληλοαποκλεισμού'}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-danger-50 text-danger-700 rounded-lg text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div>
            <label htmlFor="obligation-settings-f5" className="block text-sm font-medium text-slate-700 mb-1">
              Όνομα <span className="text-danger-600">*</span>
            </label>
            <input id="obligation-settings-f5"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              placeholder="π.χ. ΦΠΑ Περίοδος"
              required
            />
          </div>

          <div>
            <label htmlFor="oblsettings-perigrafi" className="block text-sm font-medium text-slate-700 mb-1">Περιγραφή</label>
            <textarea
              id="oblsettings-perigrafi"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              placeholder="Υποχρεώσεις που αλληλοαποκλείονται..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Τύποι Υποχρεώσεων στην ομάδα
            </label>
            <div className="border border-slate-200 rounded-lg max-h-48 overflow-y-auto">
              {activeTypes.length === 0 ? (
                <p className="p-3 text-slate-500 text-sm">Δεν υπάρχουν τύποι υποχρεώσεων.</p>
              ) : (
                activeTypes.map((type) => (
                  <label
                    key={type.id}
                    className="flex items-center gap-3 p-2 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-0"
                  >
                    <input
                      type="checkbox"
                      checked={formData.obligation_types?.includes(type.id) || false}
                      onChange={() => toggleType(type.id)}
                      className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                    />
                    <span className="text-sm text-slate-700">
                      <span className="font-medium">{type.code}</span> - {type.name}
                    </span>
                  </label>
                ))
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Οι επιλεγμένοι τύποι αλληλοαποκλείονται (μόνο ένας μπορεί να επιλεγεί ανά πελάτη).
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
            <Button type="button" variant="secondary" onClick={onClose}>
              Ακύρωση
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Αποθήκευση...' : isEdit ? 'Ενημέρωση' : 'Δημιουργία'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// VIEW TYPES MODAL (for profiles)
// ============================================

interface ViewTypesModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: ObligationProfileFull | null;
}

function ViewTypesModal({ isOpen, onClose, profile }: ViewTypesModalProps) {
  if (!isOpen || !profile) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">Τύποι στο "{profile.name}"</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150">
            <X size={20} />
          </button>
        </div>

        <div className="p-4">
          {profile.obligation_types.length === 0 ? (
            <p className="text-slate-500 text-sm text-center py-4">
              Δεν υπάρχουν τύποι σε αυτό το προφίλ.
            </p>
          ) : (
            <ul className="space-y-2">
              {profile.obligation_types.map((type) => (
                <li key={type.id} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                  <span className="px-2 py-1 text-xs font-medium bg-brand-100 text-brand-700 rounded">
                    {type.code}
                  </span>
                  <span className="text-sm text-slate-700">{type.name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex justify-end p-4 border-t border-slate-200">
          <Button variant="secondary" onClick={onClose}>
            Κλείσιμο
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// DELETE CONFIRMATION MODAL
// ============================================

interface DeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  isPending: boolean;
}

function DeleteConfirmModal({ isOpen, onClose, onConfirm, title, message, isPending }: DeleteModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-sm">
        <div className="p-4">
          <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
          <p className="text-sm text-slate-600">{message}</p>
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-slate-200">
          <Button type="button" variant="secondary" onClick={onClose}>
            Ακύρωση
          </Button>
          <Button type="button" variant="danger" onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Διαγραφή...' : 'Διαγραφή'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// MAIN COMPONENT
// ============================================

export default function ObligationSettings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('types');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [typeModalOpen, setTypeModalOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [viewTypesModalOpen, setViewTypesModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  // Edit states
  const [editingType, setEditingType] = useState<ObligationTypeFull | null>(null);
  const [editingProfile, setEditingProfile] = useState<ObligationProfileFull | null>(null);
  const [editingGroup, setEditingGroup] = useState<ObligationGroupFull | null>(null);
  const [viewingProfile, setViewingProfile] = useState<ObligationProfileFull | null>(null);
  const [deletingItem, setDeletingItem] = useState<{ type: SettingsTab; id: number; name: string } | null>(null);

  // Queries
  const { data: types = [], isLoading: typesLoading } = useObligationTypesList(
    searchQuery ? { search: searchQuery } : undefined
  );
  const { data: profiles = [], isLoading: profilesLoading } = useObligationProfilesList(
    searchQuery ? { search: searchQuery } : undefined
  );
  const { data: groups = [], isLoading: groupsLoading } = useObligationGroupsList(
    searchQuery ? { search: searchQuery } : undefined
  );

  // Delete mutations
  const deleteTypeMutation = useDeleteObligationType();
  const deleteProfileMutation = useDeleteObligationProfile();
  const deleteGroupMutation = useDeleteObligationGroup();

  const tabs = [
    { id: 'types' as const, label: 'Τύποι', icon: List, count: types.length },
    { id: 'profiles' as const, label: 'Προφίλ', icon: Layers, count: profiles.length },
    { id: 'groups' as const, label: 'Αλληλοαποκλειόμενες', icon: GitBranch, count: groups.length },
  ];

  const handleEdit = (tab: SettingsTab, item: ObligationTypeFull | ObligationProfileFull | ObligationGroupFull) => {
    if (tab === 'types') {
      setEditingType(item as ObligationTypeFull);
      setTypeModalOpen(true);
    } else if (tab === 'profiles') {
      setEditingProfile(item as ObligationProfileFull);
      setProfileModalOpen(true);
    } else {
      setEditingGroup(item as ObligationGroupFull);
      setGroupModalOpen(true);
    }
  };

  const handleDelete = (tab: SettingsTab, id: number, name: string) => {
    setDeletingItem({ type: tab, id, name });
    setDeleteModalOpen(true);
  };

  const confirmDelete = async () => {
    if (!deletingItem) return;

    try {
      if (deletingItem.type === 'types') {
        await deleteTypeMutation.mutateAsync({ id: deletingItem.id });
      } else if (deletingItem.type === 'profiles') {
        await deleteProfileMutation.mutateAsync({ id: deletingItem.id });
      } else {
        await deleteGroupMutation.mutateAsync(deletingItem.id);
      }
      setDeleteModalOpen(false);
      setDeletingItem(null);
    } catch {
      // Error handled by mutation
    }
  };

  const handleCreate = () => {
    if (activeTab === 'types') {
      setEditingType(null);
      setTypeModalOpen(true);
    } else if (activeTab === 'profiles') {
      setEditingProfile(null);
      setProfileModalOpen(true);
    } else {
      setEditingGroup(null);
      setGroupModalOpen(true);
    }
  };

  const handleViewTypes = (profile: ObligationProfileFull) => {
    setViewingProfile(profile);
    setViewTypesModalOpen(true);
  };

  const isDeletePending =
    deleteTypeMutation.isPending || deleteProfileMutation.isPending || deleteGroupMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
            <Settings className="text-brand-600" size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Ρυθμίσεις Υποχρεώσεων</h1>
            <p className="text-slate-500 text-sm">Διαχείριση τύπων, προφίλ και ομάδων υποχρεώσεων</p>
          </div>
        </div>
        <Button onClick={handleCreate}>
          <Plus size={18} className="mr-2" />
          Νέο
        </Button>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="flex border-b border-slate-200">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-brand-600 border-b-2 border-brand-600 -mb-px bg-brand-50/50'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <tab.icon size={18} />
              {tab.label}
              <span
                className={`px-2 py-0.5 text-xs rounded-full ${
                  activeTab === tab.id ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="p-4 border-b border-slate-200">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Αναζήτηση..."
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            />
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          {/* Types Tab */}
          {activeTab === 'types' && (
            <div>
              {typesLoading ? (
                <div className="text-center py-8 text-slate-500">Φόρτωση...</div>
              ) : types.length === 0 ? (
                <div className="text-center py-8">
                  <List className="mx-auto text-slate-300 mb-3" size={48} />
                  <p className="text-slate-500">Δεν υπάρχουν τύποι υποχρεώσεων.</p>
                  <p className="text-slate-400 text-sm">Προσθέστε τον πρώτο!</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left">
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Κωδικός</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Όνομα</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Συχνότητα</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Προθεσμία</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Προφίλ</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Κατάσταση</th>
                        <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Ενέργειες</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {types.map((type) => (
                        <tr key={type.id} className="hover:bg-slate-50 transition-colors duration-150">
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 text-xs font-medium bg-brand-100 text-brand-700 rounded">
                              {type.code}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">{type.name}</td>
                          <td className="px-4 py-3 text-slate-600">
                            {FREQUENCY_LABELS[type.frequency] || type.frequency}
                          </td>
                          <td className="px-4 py-3 text-slate-600">
                            {DEADLINE_TYPE_LABELS[type.deadline_type] || type.deadline_type}
                            {type.deadline_type === 'specific_day' && type.deadline_day && (
                              <span className="ml-1 text-slate-400">({type.deadline_day}η)</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-slate-600">
                            {type.profile_names && type.profile_names.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {type.profile_names.map((name, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded"
                                  >
                                    {name}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {type.is_active ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-success-100 text-success-700 rounded">
                                <CheckCircle size={12} />
                                Ενεργό
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-slate-100 text-slate-600 rounded">
                                <X size={12} />
                                Ανενεργό
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleEdit('types', type)}
                                className="p-1 text-slate-400 hover:text-brand-600 transition-colors cursor-pointer"
                                title="Επεξεργασία"
                              >
                                <Pencil size={16} />
                              </button>
                              <button
                                onClick={() => handleDelete('types', type.id, type.name)}
                                className="p-1 text-slate-400 hover:text-danger-600 transition-colors cursor-pointer"
                                title="Διαγραφή"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Profiles Tab */}
          {activeTab === 'profiles' && (
            <div>
              {profilesLoading ? (
                <div className="text-center py-8 text-slate-500">Φόρτωση...</div>
              ) : profiles.length === 0 ? (
                <div className="text-center py-8">
                  <Layers className="mx-auto text-slate-300 mb-3" size={48} />
                  <p className="text-slate-500">Δεν υπάρχουν προφίλ υποχρεώσεων.</p>
                  <p className="text-slate-400 text-sm">Προσθέστε το πρώτο!</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left">
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Όνομα</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Περιγραφή</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Πλήθος Τύπων</th>
                        <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Ενέργειες</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {profiles.map((profile) => (
                        <tr key={profile.id} className="hover:bg-slate-50">
                          <td className="px-4 py-3 font-medium text-slate-900">{profile.name}</td>
                          <td className="px-4 py-3 text-slate-600">{profile.description || '-'}</td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => handleViewTypes(profile)}
                              className="px-2 py-1 text-xs bg-brand-100 text-brand-700 rounded hover:bg-brand-200 transition-colors cursor-pointer"
                            >
                              {profile.obligation_types_count} τύποι
                            </button>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleEdit('profiles', profile)}
                                className="p-1 text-slate-400 hover:text-brand-600 transition-colors cursor-pointer"
                                title="Επεξεργασία"
                              >
                                <Pencil size={16} />
                              </button>
                              <button
                                onClick={() => handleDelete('profiles', profile.id, profile.name)}
                                className="p-1 text-slate-400 hover:text-danger-600 transition-colors cursor-pointer"
                                title="Διαγραφή"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Groups Tab */}
          {activeTab === 'groups' && (
            <div>
              {groupsLoading ? (
                <div className="text-center py-8 text-slate-500">Φόρτωση...</div>
              ) : groups.length === 0 ? (
                <div className="text-center py-8">
                  <GitBranch className="mx-auto text-slate-300 mb-3" size={48} />
                  <p className="text-slate-500">Δεν υπάρχουν ομάδες αλληλοαποκλεισμού.</p>
                  <p className="text-slate-400 text-sm">Προσθέστε την πρώτη!</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left">
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Όνομα</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Περιγραφή</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Τύποι στην Ομάδα</th>
                        <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Ενέργειες</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {groups.map((group) => (
                        <tr key={group.id} className="hover:bg-slate-50">
                          <td className="px-4 py-3 font-medium text-slate-900">{group.name}</td>
                          <td className="px-4 py-3 text-slate-600">{group.description || '-'}</td>
                          <td className="px-4 py-3">
                            {group.obligation_type_names.length === 0 ? (
                              <span className="text-slate-400">Κανένας</span>
                            ) : (
                              <div className="flex flex-wrap gap-1">
                                {group.obligation_type_names.map((name, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 text-xs bg-warning-100 text-warning-700 rounded"
                                  >
                                    {name}
                                  </span>
                                ))}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleEdit('groups', group)}
                                className="p-1 text-slate-400 hover:text-brand-600 transition-colors cursor-pointer"
                                title="Επεξεργασία"
                              >
                                <Pencil size={16} />
                              </button>
                              <button
                                onClick={() => handleDelete('groups', group.id, group.name)}
                                className="p-1 text-slate-400 hover:text-danger-600 transition-colors cursor-pointer"
                                title="Διαγραφή"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <ObligationTypeModal
        isOpen={typeModalOpen}
        onClose={() => {
          setTypeModalOpen(false);
          setEditingType(null);
        }}
        type={editingType}
        profiles={profiles}
        groups={groups}
      />

      <ObligationProfileModal
        isOpen={profileModalOpen}
        onClose={() => {
          setProfileModalOpen(false);
          setEditingProfile(null);
        }}
        profile={editingProfile}
        allTypes={types}
      />

      <ObligationGroupModal
        isOpen={groupModalOpen}
        onClose={() => {
          setGroupModalOpen(false);
          setEditingGroup(null);
        }}
        group={editingGroup}
        allTypes={types}
      />

      <ViewTypesModal
        isOpen={viewTypesModalOpen}
        onClose={() => {
          setViewTypesModalOpen(false);
          setViewingProfile(null);
        }}
        profile={viewingProfile}
      />

      <DeleteConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setDeletingItem(null);
        }}
        onConfirm={confirmDelete}
        title="Επιβεβαίωση Διαγραφής"
        message={`Είστε σίγουροι ότι θέλετε να διαγράψετε "${deletingItem?.name}";`}
        isPending={isDeletePending}
      />
    </div>
  );
}
