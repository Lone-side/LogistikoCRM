import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  RefreshCw,
  Save,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Users,
  Layers,
} from 'lucide-react';
import { Button } from '../../components';
import type { ObligationGroup, ObligationProfileFull } from '../../types';
import { FREQUENCY_LABELS } from '../../types';

// Props interface
export interface ClientProfileTabProps {
  groupedTypes: ObligationGroup[];
  profiles: ObligationProfileFull[];  // Add profiles
  clientProfile: { obligation_type_ids: number[]; obligation_profile_ids: number[] } | undefined;
  isLoading: boolean;
  onSave: (typeIds: number[], profileIds: number[]) => void;
  isSaving: boolean;
  onBulkAssign?: (typeIds: number[], profileIds: number[]) => void;  // Bulk assign callback
}

export default function ClientProfileTab({
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
  const [, setShowBulkAssignModal] = useState(false);

  const [previousClientProfile, setPreviousClientProfile] = useState<typeof clientProfile>(undefined);
  if (previousClientProfile !== clientProfile) {
    setPreviousClientProfile(clientProfile);
    if (clientProfile) {
      setSelectedTypeIds(new Set(clientProfile.obligation_type_ids));
      setSelectedProfileIds(new Set(clientProfile.obligation_profile_ids || []));
    }
  }

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
      setShowBulkAssignModal(true);
    }
  };

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-slate-400" />
        <p className="text-slate-500 mt-2">Φόρτωση προφίλ υποχρεώσεων...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Προφίλ Υποχρεώσεων</h3>
          <p className="text-sm text-slate-500 mt-1">
            Επιλέξτε τις υποχρεώσεις που ισχύουν για αυτόν τον πελάτη
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saveSuccess && (
            <span className="flex items-center text-success-600 text-sm">
              <CheckCircle className="w-4 h-4 mr-1" />
              Αποθηκεύτηκε
            </span>
          )}
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

      {/* Profiles Section */}
      {profiles && profiles.length > 0 && (
        <div className="border border-brand-200 rounded-lg overflow-hidden bg-brand-50/30">
          <div className="flex items-center justify-between bg-brand-100 px-4 py-3 border-b border-brand-200">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand-600" />
              <h4 className="font-medium text-brand-800">Profiles Υποχρεώσεων</h4>
              <span className="px-2 py-0.5 text-xs bg-brand-200 text-brand-700 rounded">
                {selectedProfileIds.size} επιλεγμένα
              </span>
            </div>
          </div>
          <div className="divide-y divide-brand-100">
            {profiles.map((profile) => (
              <label
                key={profile.id}
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-brand-50"
              >
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedProfileIds.has(profile.id)}
                    onChange={() => toggleProfile(profile.id)}
                    className="h-4 w-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-900">{profile.name}</span>
                    {profile.description && (
                      <span className="text-xs text-slate-500 ml-2">- {profile.description}</span>
                    )}
                  </div>
                </div>
                <span className="px-2 py-1 text-xs bg-brand-100 text-brand-700 rounded">
                  {profile.obligation_types_count} τύποι
                </span>
              </label>
            ))}
          </div>
          <div className="px-4 py-2 bg-brand-50 text-xs text-brand-700 border-t border-brand-200">
            Τα profiles περιλαμβάνουν προκαθορισμένες ομάδες υποχρεώσεων
          </div>
        </div>
      )}

      {/* Exclusion warning */}
      {exclusionWarning && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {exclusionWarning}
        </div>
      )}

      {/* Groups */}
      {groupedTypes.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          Δεν υπάρχουν διαθέσιμοι τύποι υποχρεώσεων.
        </div>
      ) : (
        <div className="space-y-6">
          {groupedTypes.map((group) => {
            const isExclusionGroup = group.group_id !== null;
            return (
              <div key={group.group_id || 'ungrouped'} className="border border-slate-200 rounded-lg overflow-hidden">
                {/* Group Header */}
                <div className="flex items-center justify-between bg-slate-50 px-4 py-3 border-b border-slate-200">
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-slate-900">{group.group_name}</h4>
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
                    className="text-sm text-brand-600 hover:text-brand-800"
                  >
                    {isAllSelectedInGroup(group) ? 'Αποεπιλογή όλων' : isExclusionGroup ? 'Επιλογή' : 'Επιλογή όλων'}
                  </button>
                </div>

                {/* Types List */}
                <div className="divide-y divide-slate-100">
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
                            ? 'bg-slate-50 opacity-60'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type={isExclusionGroup ? 'radio' : 'checkbox'}
                            name={isExclusionGroup ? `exclusion-group-${group.group_id}` : undefined}
                            checked={isSelected}
                            onChange={() => toggleType(type.id)}
                            className={`h-4 w-4 text-brand-600 border-slate-300 focus:ring-brand-500 ${
                              isExclusionGroup ? '' : 'rounded'
                            }`}
                          />
                          <div>
                            <span className="text-sm font-medium text-slate-900">{type.name}</span>
                            <span className="text-xs text-slate-500 ml-2">({type.code})</span>
                          </div>
                        </div>
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded ${
                            type.frequency === 'monthly'
                              ? 'bg-brand-100 text-brand-800'
                              : type.frequency === 'quarterly'
                              ? 'bg-purple-100 text-purple-800'
                              : type.frequency === 'annual'
                              ? 'bg-success-100 text-success-700'
                              : 'bg-slate-100 text-slate-800'
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

      {/* Summary */}
      <div className="bg-slate-50 rounded-lg p-4">
        <p className="text-sm text-slate-600">
          <span className="font-medium text-slate-900">{selectedTypeIds.size}</span> υποχρεώσεις επιλεγμένες
          {selectedProfileIds.size > 0 && (
            <span className="ml-2">
              + <span className="font-medium text-brand-600">{selectedProfileIds.size}</span> profiles
            </span>
          )}
        </p>
      </div>

      {/* Link to Obligation Settings */}
      <div className="text-center">
        <Link
          to="/settings/obligations"
          className="text-sm text-brand-600 hover:text-brand-800 hover:underline"
        >
          Διαχείριση τύπων υποχρεώσεων
          <ExternalLink className="w-3 h-3 inline ml-1" />
        </Link>
      </div>
    </div>
  );
}
