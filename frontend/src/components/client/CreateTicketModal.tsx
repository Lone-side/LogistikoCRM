import { useState } from 'react';
import {
  Plus,
  RefreshCw,
  X,
} from 'lucide-react';
import { Button } from '../../components';

// Props interface
export interface CreateTicketModalProps {
  onClose: () => void;
  onCreate: (title: string, description?: string, priority?: 'low' | 'medium' | 'high' | 'urgent') => void;
  isLoading: boolean;
}

export default function CreateTicketModal({
  onClose,
  onCreate,
  isLoading,
}: CreateTicketModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium');

  const handleSubmit = () => {
    if (title.trim()) {
      onCreate(title, description, priority);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">Νέο Ticket</h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Τίτλος *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg"
              placeholder="Π.χ. Επικοινωνία για ΦΠΑ"
              autoFocus
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Περιγραφή
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg resize-none"
              placeholder="Λεπτομέρειες..."
            />
          </div>

          {/* Priority */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Προτεραιότητα
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as typeof priority)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg"
            >
              <option value="low">Χαμηλή</option>
              <option value="medium">Μεσαία</option>
              <option value="high">Υψηλή</option>
              <option value="urgent">Επείγον</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-3 p-4 border-t bg-slate-50">
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Ακύρωση
          </Button>
          <Button onClick={handleSubmit} disabled={!title.trim() || isLoading}>
            {isLoading ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-2" />
            )}
            Δημιουργία
          </Button>
        </div>
      </div>
    </div>
  );
}
