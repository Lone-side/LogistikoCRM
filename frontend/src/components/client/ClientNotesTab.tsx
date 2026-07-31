import { useState } from 'react';
import type { ClientFull } from '../../types';

// Props interface
export interface ClientNotesTabProps {
  client: ClientFull;
  isEditing: boolean;
  onFieldChange: (field: keyof ClientFull, value: unknown) => void;
}

export default function ClientNotesTab({
  isEditing,
}: ClientNotesTabProps) {
  // Note: simeiosis_pelati field doesn't exist in the current model
  // This is a placeholder for future implementation
  const [notes, setNotes] = useState('');

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-slate-700">Σημειώσεις Πελάτη</h3>
      {isEditing ? (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={10}
          className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 resize-none"
          placeholder="Προσθέστε σημειώσεις για τον πελάτη..."
        />
      ) : (
        <div className="bg-slate-50 rounded-lg p-4 min-h-[200px]">
          {notes ? (
            <p className="whitespace-pre-wrap text-slate-700">{notes}</p>
          ) : (
            <p className="text-slate-400 italic">Δεν υπάρχουν σημειώσεις. Η λειτουργία αυτή θα προστεθεί σύντομα.</p>
          )}
        </div>
      )}
    </div>
  );
}
