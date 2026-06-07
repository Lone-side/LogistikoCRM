import { useState, useEffect, type FormEvent } from 'react';
import { Button } from './Button';
import { useObligationTypes } from '../hooks/useObligations';
import { useUsers } from '../hooks/useUsers';
import type { Client, Obligation, ObligationFormData, ObligationStatus } from '../types';
import {
  OBLIGATION_STATUS_OPTIONS as STATUS_OPTIONS,
  MONTHS,
  YEARS,
} from '../constants';

interface ObligationFormProps {
  obligation?: Obligation | null;
  clients: Client[];
  onSubmit: (data: ObligationFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const currentYear = new Date().getFullYear();

export function ObligationForm({
  obligation,
  clients,
  onSubmit,
  onCancel,
  isLoading = false,
}: ObligationFormProps) {
  // Fetch obligation types dynamically from API
  const { data: obligationTypes, isLoading: typesLoading } = useObligationTypes();
  // Fetch users for assignment dropdown
  const { data: usersData, isLoading: usersLoading } = useUsers();
  const users = usersData?.users || [];

  const [formData, setFormData] = useState<ObligationFormData>({
    client: 0,
    obligation_type: 0,
    month: new Date().getMonth() + 1,
    year: currentYear,
    deadline: '',
    status: 'pending',
    completed_date: null,
    time_spent: null,
    notes: '',
    assigned_to: null,
  });
  const [errors, setErrors] = useState<Partial<Record<keyof ObligationFormData, string>>>({});

  // Set default obligation type when types are loaded
  useEffect(() => {
    if (obligationTypes && obligationTypes.length > 0 && formData.obligation_type === 0) {
      setFormData((prev) => ({ ...prev, obligation_type: obligationTypes[0].id }));
    }
  }, [obligationTypes, formData.obligation_type]);

  // Populate form when editing
  useEffect(() => {
    if (obligation) {
      setFormData({
        client: obligation.client,
        obligation_type: obligation.obligation_type,
        month: obligation.month,
        year: obligation.year,
        deadline: obligation.deadline,
        status: obligation.status,
        completed_date: obligation.completed_date || null,
        time_spent: obligation.time_spent || null,
        notes: obligation.notes || '',
        assigned_to: obligation.assigned_to || null,
      });
    }
  }, [obligation]);

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof ObligationFormData, string>> = {};

    if (!formData.client) {
      newErrors.client = 'Επιλέξτε πελάτη';
    }

    if (!formData.obligation_type) {
      newErrors.obligation_type = 'Επιλέξτε τύπο υποχρέωσης';
    }

    if (!formData.deadline) {
      newErrors.deadline = 'Η προθεσμία είναι υποχρεωτική';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit(formData);
    }
  };

  const handleChange = <K extends keyof ObligationFormData>(field: K, value: ObligationFormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Πελάτης */}
      <div>
        <label htmlFor="client" className="block text-sm font-medium text-gray-700 mb-1">
          Πελάτης *
        </label>
        <select
          id="client"
          value={formData.client}
          onChange={(e) => handleChange('client', Number(e.target.value))}
          className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
            errors.client ? 'border-red-500' : 'border-gray-300'
          }`}
        >
          <option value={0}>-- Επιλέξτε πελάτη --</option>
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.eponimia} ({client.afm})
            </option>
          ))}
        </select>
        {errors.client && <p className="mt-1 text-sm text-red-500">{errors.client}</p>}
      </div>

      {/* Τύπος Υποχρέωσης - Dynamic from API */}
      <div>
        <label htmlFor="obligation_type" className="block text-sm font-medium text-gray-700 mb-1">
          Τύπος Υποχρέωσης *
        </label>
        <select
          id="obligation_type"
          value={formData.obligation_type}
          onChange={(e) => handleChange('obligation_type', Number(e.target.value))}
          disabled={typesLoading}
          className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
            errors.obligation_type ? 'border-red-500' : 'border-gray-300'
          } ${typesLoading ? 'bg-gray-100' : ''}`}
        >
          {typesLoading ? (
            <option value={0}>Φόρτωση τύπων...</option>
          ) : (
            <>
              <option value={0}>-- Επιλέξτε τύπο --</option>
              {obligationTypes?.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.code} - {type.name}
                </option>
              ))}
            </>
          )}
        </select>
        {errors.obligation_type && (
          <p className="mt-1 text-sm text-red-500">{errors.obligation_type}</p>
        )}
      </div>

      {/* Περίοδος */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="month" className="block text-sm font-medium text-gray-700 mb-1">
            Μήνας
          </label>
          <select
            id="month"
            value={formData.month}
            onChange={(e) => handleChange('month', Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          >
            {MONTHS.map((month) => (
              <option key={month.value} value={month.value}>
                {month.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="year" className="block text-sm font-medium text-gray-700 mb-1">
            Έτος
          </label>
          <select
            id="year"
            value={formData.year}
            onChange={(e) => handleChange('year', Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          >
            {YEARS.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Προθεσμία */}
      <div>
        <label htmlFor="deadline" className="block text-sm font-medium text-gray-700 mb-1">
          Προθεσμία *
        </label>
        <input
          type="date"
          id="deadline"
          value={formData.deadline}
          onChange={(e) => handleChange('deadline', e.target.value)}
          className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
            errors.deadline ? 'border-red-500' : 'border-gray-300'
          }`}
        />
        {errors.deadline && <p className="mt-1 text-sm text-red-500">{errors.deadline}</p>}
      </div>

      {/* Κατάσταση */}
      <div>
        <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
          Κατάσταση
        </label>
        <select
          id="status"
          value={formData.status}
          onChange={(e) => handleChange('status', e.target.value as ObligationStatus)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        >
          {STATUS_OPTIONS.map((status) => (
            <option key={status.value} value={status.value}>
              {status.label}
            </option>
          ))}
        </select>
      </div>

      {/* Ανάθεση σε */}
      <div>
        <label htmlFor="assigned_to" className="block text-sm font-medium text-gray-700 mb-1">
          Ανάθεση σε
        </label>
        <select
          id="assigned_to"
          value={formData.assigned_to || ''}
          onChange={(e) => handleChange('assigned_to', e.target.value ? Number(e.target.value) : null)}
          disabled={usersLoading}
          className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
            usersLoading ? 'bg-gray-100' : ''
          }`}
        >
          <option value="">-- Χωρίς ανάθεση --</option>
          {users.filter(u => u.is_active).map((user) => (
            <option key={user.id} value={user.id}>
              {user.first_name && user.last_name
                ? `${user.first_name} ${user.last_name}`
                : user.username}
            </option>
          ))}
        </select>
      </div>

      {/* Ημ/νία Ολοκλήρωσης - εμφανίζεται όταν η κατάσταση είναι 'completed' */}
      {formData.status === 'completed' && (
        <div>
          <label htmlFor="completed_date" className="block text-sm font-medium text-gray-700 mb-1">
            Ημ/νία Ολοκλήρωσης
          </label>
          <input
            type="date"
            id="completed_date"
            value={formData.completed_date || ''}
            onChange={(e) => handleChange('completed_date', e.target.value || null)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
        </div>
      )}

      {/* Χρόνος Εργασίας */}
      <div>
        <label htmlFor="time_spent" className="block text-sm font-medium text-gray-700 mb-1">
          Χρόνος Εργασίας (ώρες)
        </label>
        <input
          type="number"
          id="time_spent"
          value={formData.time_spent ?? ''}
          onChange={(e) => handleChange('time_spent', e.target.value ? parseFloat(e.target.value) : null)}
          step="0.25"
          min="0"
          placeholder="π.χ. 1.5"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
      </div>

      {/* Σημειώσεις */}
      <div>
        <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
          Σημειώσεις
        </label>
        <textarea
          id="notes"
          value={formData.notes || ''}
          onChange={(e) => handleChange('notes', e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-transparent resize-none"
          placeholder="Σημειώσεις για την υποχρέωση..."
        />
      </div>

      {/* Buttons */}
      <div className="flex gap-3 pt-4 border-t border-gray-200">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isLoading}>
          Ακύρωση
        </Button>
        <Button type="submit" variant="primary" isLoading={isLoading}>
          {obligation ? 'Αποθήκευση' : 'Δημιουργία'}
        </Button>
      </div>
    </form>
  );
}

export default ObligationForm;
