import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  RefreshCw,
  Save,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Users,
  Layers,
  Copy,
  ChevronDown,
  ChevronRight,
  Zap,
  Search,
  X,
  FileText,
} from 'lucide-react';
import { Button } from '../../components';
import type { ObligationGroup, ObligationProfileFull } from '../../types';
import { FREQUENCY_LABELS } from '../../types';
import {
  useClientsWithObligationStatus,
  useClientObligationProfile,
} from '../../hooks/useObligations';

// Props interface
export interface ClientProfileTabProps {
  clientId?: number;
  groupedTypes: ObligationGroup[];
  profiles: ObligationProfileFull[];
  clientProfile: { obligation_type_ids: number[]; obligation_profile_ids: number[] } | undefined;
  isLoading: boolean;
  onSave: (typeIds: number[], profileIds: number[]) => void;
  isSaving: boolean;
  onBulkAssign?: (typeIds: number[], profileIds: number[]) => void;
}

export default function ClientProfileTab({
  clientId,
  groupedTypes,
  profiles,
  clientProfile,
  isLoading,
  onSave,
  isSaving,
  onBulkAssign,
}: ClientProfileTabProps) {
  // Local state for selected obligations
  const [selectedTypeIds, setSelectedTypeIds] = useState<Set<number>>(new Set());
  const [selectedProfileIds, setSelectedProfileIds] = useState<Set<number>>(new Set());
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [exclusionWarning, setExclusionWarning] = useState<string | null>(null);
  const [showCopyModal, setShowCopyModal] = useState(false);
  const [expandedProfiles, setExpandedProfiles] = useState<Set<number>>(new Set());
  const profilesSectionRef = useRef<HTMLDivElement>(null);
  const typesSectionRef = useRef<HTMLDivElement>(null);

  // Initialize from client profile when it loads
  useEffect(() => {
    if (clientProfile) {
      setSelectedTypeIds(new Set(clientProfile.obligation_type_ids));
      setSelectedProfileIds(new Set(clientProfile.obligation_profile_ids || []));
    }
  }, [clientProfile]);

  // Toggle profile selection
  const toggleProfile = (profileId: number) => {
    const newSelected = new Set(selectedProfileIds);
    if (newSelected.has(profileId)) {
      newSelected.delete(profileId);
    } else {
      newSelected.add(profileId);
    }
    setSelectedProfileIds(newSelected);
    setHasChanges(true);
    setSaveSuccess(false);
  };

  // Build a map of type id to group info for exclusion logic
  const typeToGroupMap = new Map<number, { groupId: number | null; groupName: string; types: typeof groupedTypes[0]['types'] }>();
  groupedTypes.forEach((group) => {
    // Only groups with non-null group_id are exclusion groups
    if (group.group_id !== null) {
      group.types.forEach((t) => {
        typeToGroupMap.set(t.id, {
          groupId: group.group_id,
          groupName: group.group_name,
          types: group.types,
        });
      });
    }
  });

  // Toggle a single obligation type with exclusion logic
  const toggleType = (typeId: number) => {
    const newSelected = new Set(selectedTypeIds);
    setExclusionWarning(null);

    if (newSelected.has(typeId)) {
      // Simple deselection
      newSelected.delete(typeId);
    } else {
      // Check for exclusion group
      const groupInfo = typeToGroupMap.get(typeId);

      if (groupInfo && groupInfo.groupId !== null) {
        // Find other selected types in the same exclusion group
        const otherSelectedInGroup = groupInfo.types
          .filter((t) => t.id !== typeId && newSelected.has(t.id));

        if (otherSelectedInGroup.length > 0) {
          // Deselect other types in the exclusion group
          otherSelectedInGroup.forEach((t) => newSelected.delete(t.id));

          // Show warning
          const deselectedNames = otherSelectedInGroup.map((t) => t.name).join(', ');
          setExclusionWarning(`Η επιλογή αυτή αντικαθιστά: ${deselectedNames}`);

          // Clear warning after 5 seconds
          setTimeout(() => setExclusionWarning(null), 5000);
        }
      }

      newSelected.add(typeId);
    }

    setSelectedTypeIds(newSelected);
    setHasChanges(true);
    setSaveSuccess(false);
  };

  // Select all in a group (skip for exclusion groups - only allow one)
  const selectAllInGroup = (group: ObligationGroup) => {
    const newSelected = new Set(selectedTypeIds);

    if (group.group_id !== null) {
      // For exclusion groups, just select the first one if none selected
      const hasAnySelected = group.types.some((t) => newSelected.has(t.id));
      if (!hasAnySelected && group.types.length > 0) {
        newSelected.add(group.types[0].id);
      }
    } else {
      // For non-exclusion groups, select all
      group.types.forEach((t) => newSelected.add(t.id));
    }

    setSelectedTypeIds(newSelected);
    setHasChanges(true);
    setSaveSuccess(false);
  };

  // Deselect all in a group
  const deselectAllInGroup = (group: ObligationGroup) => {
    const newSelected = new Set(selectedTypeIds);
    group.types.forEach((t) => newSelected.delete(t.id));
    setSelectedTypeIds(newSelected);
    setHasChanges(true);
    setSaveSuccess(false);
    setExclusionWarning(null);
  };

  // Check if all in group are selected (for exclusion groups, check if any is selected)
  const isAllSelectedInGroup = (group: ObligationGroup) => {
    if (group.group_id !== null) {
      // For exclusion groups, check if any type is selected
      return group.types.some((t) => selectedTypeIds.has(t.id));
    }
    return group.types.every((t) => selectedTypeIds.has(t.id));
  };

  // Handle save
  const handleSave = () => {
    onSave(Array.from(selectedTypeIds), Array.from(selectedProfileIds));
    setHasChanges(false);
    setSaveSuccess(true);
    setExclusionWarning(null);
    // Reset success message after 3 seconds
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  // Handle bulk assign
  const handleBulkAssign = () => {
    if (onBulkAssign) {
      onBulkAssign(Array.from(selectedTypeIds), Array.from(selectedProfileIds));
    }
  };

  // Toggle profile expand/collapse
  const toggleProfileExpand = (profileId: number) => {
    const newExpanded = new Set(expandedProfiles);
    if (newExpanded.has(profileId)) {
      newExpanded.delete(profileId);
    } else {
      newExpanded.add(profileId);
    }
    setExpandedProfiles(newExpanded);
  };

  // Quick-apply: select only this profile, deselect everything else
  const quickApplyProfile = (profileId: number) => {
    setSelectedProfileIds(new Set([profileId]));
    setSelectedTypeIds(new Set());
    setHasChanges(true);
    setSaveSuccess(false);
  };

  // Apply copied obligations from another client.
  // Enforce exclusion groups: keep the first type seen per group, drop the rest.
  const applyCopiedObligations = (typeIds: number[], profileIds: number[]) => {
    const accepted = new Set<number>();
    const seenGroups = new Set<number>();
    const droppedNames: string[] = [];

    for (const id of typeIds) {
      const groupInfo = typeToGroupMap.get(id);
      if (groupInfo && groupInfo.groupId !== null) {
        if (seenGroups.has(groupInfo.groupId)) {
          const t = groupInfo.types.find(x => x.id === id);
          if (t) droppedNames.push(t.name);
          continue;
        }
        seenGroups.add(groupInfo.groupId);
      }
      accepted.add(id);
    }

    setSelectedTypeIds(accepted);
    setSelectedProfileIds(new Set(profileIds));
    setHasChanges(true);
    setSaveSuccess(false);
    setShowCopyModal(false);

    if (droppedNames.length > 0) {
      setExclusionWarning(
        `Παραλείφθηκαν λόγω αλληλοαποκλεισμού: ${droppedNames.join(', ')}`
      );
      setTimeout(() => setExclusionWarning(null), 6000);
    }
  };

  // Count total types including from profiles
  const profileTypesCount = profiles
    .filter(p => selectedProfileIds.has(p.id))
    .reduce((sum, p) => sum + p.obligation_types_count, 0);

  const isEmpty = selectedTypeIds.size === 0 && selectedProfileIds.size === 0;
  const isInitialEmpty = isEmpty && !hasChanges;

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
        <p className="text-gray-500 mt-2">Φόρτωση προφίλ υποχρεώσεων...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Προφίλ Υποχρεώσεων</h3>
          <p className="text-sm text-gray-500 mt-1">
            Επιλέξτε τις υποχρεώσεις που ισχύουν για αυτόν τον πελάτη
          </p>
        </div>
        <div className="flex items-center gap-2">
          {saveSuccess && (
            <span className="flex items-center text-green-600 text-sm">
              <CheckCircle className="w-4 h-4 mr-1" />
              Αποθηκεύτηκε
            </span>
          )}
          <Button
            variant="secondary"
            onClick={() => setShowCopyModal(true)}
            title="Αντιγραφή υποχρεώσεων από άλλον πελάτη"
          >
            <Copy className="w-4 h-4 mr-2" />
            Αντιγραφή από πελάτη
          </Button>
          {onBulkAssign && (
            <Button
              variant="secondary"
              onClick={handleBulkAssign}
              disabled={selectedTypeIds.size === 0 && selectedProfileIds.size === 0}
              title="Ανάθεση αυτών των επιλογών σε πολλούς πελάτες"
            >
              <Users className="w-4 h-4 mr-2" />
              Μαζική Ανάθεση
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Αποθήκευση
          </Button>
        </div>
      </div>

      {/* Empty State Guide */}
      {isInitialEmpty && (
        <div className="border-2 border-dashed border-blue-300 rounded-lg p-6 bg-blue-50/50 text-center">
          <FileText className="w-10 h-10 mx-auto text-blue-400 mb-3" />
          <h4 className="text-base font-medium text-gray-900 mb-1">
            Δεν έχουν οριστεί υποχρεώσεις
          </h4>
          <p className="text-sm text-gray-500 mb-4">
            Επιλέξτε πώς θέλετε να ορίσετε υποχρεώσεις για αυτόν τον πελάτη:
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {profiles.length > 0 && (
              <Button
                variant="secondary"
                onClick={() => profilesSectionRef.current?.scrollIntoView({ behavior: 'smooth' })}
              >
                <Layers className="w-4 h-4 mr-2" />
                Επιλέξτε Profile
              </Button>
            )}
            <Button
              variant="secondary"
              onClick={() => setShowCopyModal(true)}
            >
              <Copy className="w-4 h-4 mr-2" />
              Αντιγραφή από πελάτη
            </Button>
            <Button
              variant="secondary"
              onClick={() => typesSectionRef.current?.scrollIntoView({ behavior: 'smooth' })}
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Επιλέξτε χειροκίνητα
            </Button>
          </div>
        </div>
      )}

      {/* Profiles Section */}
      <div ref={profilesSectionRef}>
        {profiles && profiles.length > 0 ? (
          <div className="border border-blue-200 rounded-lg overflow-hidden bg-blue-50/30">
            <div className="flex items-center justify-between bg-blue-100 px-4 py-3 border-b border-blue-200">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <h4 className="font-medium text-blue-900">Profiles Υποχρεώσεων</h4>
                <span className="px-2 py-0.5 text-xs bg-blue-200 text-blue-700 rounded">
                  {selectedProfileIds.size} επιλεγμένα
                </span>
              </div>
            </div>
            <div className="divide-y divide-blue-100">
              {profiles.map((profile) => (
                <div key={profile.id}>
                  <div className="flex items-center justify-between px-4 py-3 hover:bg-blue-50">
                    <div className="flex items-center gap-3 flex-1">
                      <input
                        type="checkbox"
                        checked={selectedProfileIds.has(profile.id)}
                        onChange={() => toggleProfile(profile.id)}
                        className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-brand-500"
                      />
                      <button
                        type="button"
                        onClick={() => toggleProfileExpand(profile.id)}
                        className="flex items-center gap-2 text-left flex-1"
                      >
                        {expandedProfiles.has(profile.id) ? (
                          <ChevronDown className="w-4 h-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-gray-400" />
                        )}
                        <div>
                          <span className="text-sm font-medium text-gray-900">{profile.name}</span>
                          {profile.description && (
                            <span className="text-xs text-gray-500 ml-2">- {profile.description}</span>
                          )}
                        </div>
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => quickApplyProfile(profile.id)}
                        className="px-2 py-1 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-100 rounded transition-colors"
                        title="Εφαρμογή μόνο αυτού του profile"
                      >
                        <Zap className="w-3 h-3 inline mr-1" />
                        Γρήγορη εφαρμογή
                      </button>
                      <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded">
                        {profile.obligation_types_count} τύποι
                      </span>
                    </div>
                  </div>
                  {/* Expanded types list */}
                  {expandedProfiles.has(profile.id) && profile.obligation_types.length > 0 && (
                    <div className="px-12 pb-3 bg-blue-50/50">
                      <div className="text-xs text-gray-500 mb-1">Περιλαμβάνει:</div>
                      <div className="flex flex-wrap gap-1">
                        {profile.obligation_types.map((t) => (
                          <span
                            key={t.id}
                            className="px-2 py-0.5 text-xs bg-white border border-blue-200 text-blue-800 rounded"
                          >
                            {t.name} ({t.code})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="px-4 py-2 bg-blue-50 text-xs text-blue-700 border-t border-blue-200">
              Κλικ στο βέλος για να δείτε τους τύπους κάθε profile
            </div>
          </div>
        ) : (
          <div className="border border-dashed border-gray-300 rounded-lg p-4 text-center text-sm text-gray-500">
            Δεν υπάρχουν profiles.{' '}
            <Link to="/settings/obligations" className="text-blue-600 hover:underline">
              Δημιουργήστε στις Ρυθμίσεις
              <ExternalLink className="w-3 h-3 inline ml-1" />
            </Link>
          </div>
        )}
      </div>

      {/* Exclusion warning */}
      {exclusionWarning && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {exclusionWarning}
        </div>
      )}

      {/* Groups */}
      <div ref={typesSectionRef}>
        {groupedTypes.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Δεν υπάρχουν διαθέσιμοι τύποι υποχρεώσεων.
          </div>
        ) : (
          <div className="space-y-6">
            {groupedTypes.map((group) => {
              const isExclusionGroup = group.group_id !== null;
              return (
                <div key={group.group_id || 'ungrouped'} className="border border-gray-200 rounded-lg overflow-hidden">
                  {/* Group Header */}
                  <div className="flex items-center justify-between bg-gray-50 px-4 py-3 border-b border-gray-200">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-gray-900">{group.group_name}</h4>
                      {isExclusionGroup && (
                        <span className="px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded">
                          Αλληλοαποκλειόμενες
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() =>
                        isAllSelectedInGroup(group)
                          ? deselectAllInGroup(group)
                          : selectAllInGroup(group)
                      }
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      {isAllSelectedInGroup(group) ? 'Αποεπιλογή όλων' : isExclusionGroup ? 'Επιλογή' : 'Επιλογή όλων'}
                    </button>
                  </div>

                  {/* Types List */}
                  <div className="divide-y divide-gray-100">
                    {group.types.map((type) => {
                      const isSelected = selectedTypeIds.has(type.id);
                      const isDisabledByExclusion = isExclusionGroup &&
                        !isSelected &&
                        group.types.some((t) => t.id !== type.id && selectedTypeIds.has(t.id));

                      return (
                        <label
                          key={type.id}
                          className={`flex items-center justify-between px-4 py-3 cursor-pointer ${
                            isDisabledByExclusion
                              ? 'bg-gray-50 opacity-60'
                              : 'hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <input
                              type={isExclusionGroup ? 'radio' : 'checkbox'}
                              name={isExclusionGroup ? `exclusion-group-${group.group_id}` : undefined}
                              checked={isSelected}
                              onChange={() => toggleType(type.id)}
                              className={`h-4 w-4 text-blue-600 border-gray-300 focus:ring-brand-500 ${
                                isExclusionGroup ? '' : 'rounded'
                              }`}
                            />
                            <div>
                              <span className="text-sm font-medium text-gray-900">{type.name}</span>
                              <span className="text-xs text-gray-500 ml-2">({type.code})</span>
                            </div>
                          </div>
                          <span
                            className={`px-2 py-1 text-xs font-medium rounded ${
                              type.frequency === 'monthly'
                                ? 'bg-blue-100 text-blue-800'
                                : type.frequency === 'quarterly'
                                ? 'bg-purple-100 text-purple-800'
                                : type.frequency === 'annual'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {FREQUENCY_LABELS[type.frequency] || type.frequency}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <p className="text-sm text-gray-600">
          <span className="font-medium text-gray-900">{selectedTypeIds.size}</span> μεμονωμένοι τύποι
          {selectedProfileIds.size > 0 && (
            <span className="ml-2">
              + <span className="font-medium text-blue-600">{selectedProfileIds.size}</span> profiles
              <span className="text-gray-400 ml-1">({profileTypesCount} τύποι)</span>
            </span>
          )}
          {(selectedTypeIds.size > 0 || selectedProfileIds.size > 0) && (
            <span className="ml-2 text-gray-400">
              = Σύνολο: {selectedTypeIds.size + profileTypesCount} υποχρεώσεις
            </span>
          )}
        </p>
      </div>

      {/* Link to Obligation Settings */}
      <div className="text-center">
        <Link
          to="/settings/obligations"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
        >
          Διαχείριση τύπων υποχρεώσεων
          <ExternalLink className="w-3 h-3 inline ml-1" />
        </Link>
      </div>

      {/* Copy From Client Modal */}
      {showCopyModal && (
        <CopyFromClientModal
          currentClientId={clientId}
          onApply={applyCopiedObligations}
          onClose={() => setShowCopyModal(false)}
        />
      )}
    </div>
  );
}

// ============================================
// COPY FROM CLIENT MODAL
// ============================================

interface CopyFromClientModalProps {
  currentClientId?: number;
  onApply: (typeIds: number[], profileIds: number[]) => void;
  onClose: () => void;
}

function CopyFromClientModal({ currentClientId, onApply, onClose }: CopyFromClientModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const { data: clients, isLoading } = useClientsWithObligationStatus();
  const { data: selectedProfile } = useClientObligationProfile(selectedClientId || 0);

  const filteredClients = (clients || [])
    .filter(c => c.id !== currentClientId && c.has_obligation_profile)
    .filter(c =>
      searchTerm === '' ||
      c.eponimia.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.afm.includes(searchTerm)
    );

  const handleApply = () => {
    if (selectedProfile) {
      onApply(
        selectedProfile.obligation_type_ids || [],
        selectedProfile.obligation_profile_ids || []
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Αντιγραφή από πελάτη</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-3 border-b">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Αναζήτηση με επωνυμία ή ΑΦΜ..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-blue-500"
              autoFocus
            />
          </div>
        </div>

        {/* Client list */}
        <div className="flex-1 overflow-y-auto px-6 py-2">
          {isLoading ? (
            <div className="text-center py-8">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" />
            </div>
          ) : filteredClients.length === 0 ? (
            <div className="text-center py-8 text-sm text-gray-500">
              {searchTerm ? 'Δεν βρέθηκαν πελάτες' : 'Δεν υπάρχουν πελάτες με υποχρεώσεις'}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredClients.map(client => (
                <button
                  key={client.id}
                  type="button"
                  onClick={() => setSelectedClientId(client.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                    selectedClientId === client.id
                      ? 'bg-blue-100 border border-blue-300'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-gray-900">{client.eponimia}</span>
                      <span className="text-xs text-gray-500 ml-2">ΑΦΜ: {client.afm}</span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {client.obligation_types_count} υποχρ.
                    </span>
                  </div>
                  {client.obligation_profile_names.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {client.obligation_profile_names.map((name, i) => (
                        <span key={i} className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-700 rounded">
                          {name}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t">
          <Button variant="secondary" onClick={onClose}>
            Ακύρωση
          </Button>
          <Button
            onClick={handleApply}
            disabled={!selectedClientId || !selectedProfile}
          >
            <Copy className="w-4 h-4 mr-2" />
            Αντιγραφή
          </Button>
        </div>
      </div>
    </div>
  );
}
