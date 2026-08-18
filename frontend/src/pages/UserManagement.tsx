import { useState } from 'react';
import {
  Users,
  Plus,
  Pencil,
  Trash2,
  UserCheck,
  UserX,
  Shield,
  Search,
  RefreshCw,
  Eye,
  EyeOff,
} from 'lucide-react';
import { Button } from '../components';
import { PageHeader } from '../components/ui';
import { useToast } from '../hooks/useToast';
import ConfirmDialog from '../components/ConfirmDialog';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useToggleUserActive,
  type User,
  type UserCreate,
  type UserUpdate,
} from '../hooks/useUsers';
import { useAuthStore } from '../stores/authStore';

export default function UserManagement() {
  const { user: currentUser } = useAuthStore();
  const { data, isLoading, refetch, isRefetching } = useUsers();
  const { showToast } = useToast();

  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);

  // Filter users based on search
  const filteredUsers = data?.users?.filter((user) => {
    const query = searchQuery.toLowerCase();
    return (
      user.username.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query) ||
      user.first_name?.toLowerCase().includes(query) ||
      user.last_name?.toLowerCase().includes(query)
    );
  }) || [];

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setIsModalOpen(true);
  };

  const handleCreate = () => {
    setEditingUser(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingUser(null);
  };

  const handleDelete = (user: User) => {
    setDeletingUser(user);
  };

  // Check if current user can edit the target user
  const canEdit = (targetUser: User): boolean => {
    if (currentUser?.is_superuser) return true;
    if (targetUser.is_superuser) return false;
    return currentUser?.is_staff ?? false;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Users className="text-brand-600" />
            Διαχείριση Χρηστών
          </span>
        }
        subtitle="Διαχείριση λογαριασμών χρηστών του συστήματος"
        actions={
          <Button onClick={handleCreate}>
            <Plus size={18} className="mr-2" />
            Νέος Χρήστης
          </Button>
        }
      />

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search
              size={18}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              placeholder="Αναζήτηση χρήστη..."
              aria-label="Αναζήτηση χρήστη"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
            />
          </div>
          <Button
            variant="secondary"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            <RefreshCw
              size={18}
              className={isRefetching ? 'animate-spin' : ''}
            />
          </Button>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <RefreshCw size={24} className="animate-spin mx-auto mb-2 text-brand-600" />
            <p className="text-slate-500">Φόρτωση χρηστών...</p>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="p-8 text-center">
            <Users size={48} className="mx-auto mb-4 text-slate-300" />
            <p className="text-slate-500">Δεν βρέθηκαν χρήστες</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Χρήστης
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Ρόλος
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Κατάσταση
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Τελευταία Σύνδεση
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Ενέργειες
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredUsers.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    currentUser={currentUser}
                    canEdit={canEdit(user)}
                    onEdit={() => handleEdit(user)}
                    onDelete={() => handleDelete(user)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Count */}
        {!isLoading && (
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 text-sm text-slate-500">
            {filteredUsers.length} χρήστ{filteredUsers.length === 1 ? 'ης' : 'ες'}
          </div>
        )}
      </div>

      {/* User Modal */}
      {isModalOpen && (
        <UserModal
          user={editingUser}
          onClose={handleCloseModal}
          showToast={showToast}
        />
      )}

      {/* Delete Confirmation */}
      <DeleteUserDialog
        user={deletingUser}
        onClose={() => setDeletingUser(null)}
        showToast={showToast}
      />
    </div>
  );
}

// ============================================
// USER ROW COMPONENT
// ============================================

interface UserRowProps {
  user: User;
  currentUser: { id: number; is_superuser?: boolean } | null;
  canEdit: boolean;
  onEdit: () => void;
  onDelete: () => void;
}

function UserRow({ user, currentUser, canEdit, onEdit, onDelete }: UserRowProps) {
  const toggleActive = useToggleUserActive();
  const { showToast } = useToast();

  const handleToggleActive = async () => {
    try {
      const result = await toggleActive.mutateAsync(user.id);
      showToast('success', result.message || 'Η κατάσταση άλλαξε');
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : 'Σφάλμα';
      showToast('error', errMsg);
    }
  };

  const isCurrentUser = currentUser?.id === user.id;
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('el-GR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <tr className={`hover:bg-slate-50 ${!user.is_active ? 'opacity-60' : ''}`}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-100 rounded-full flex items-center justify-center">
            <span className="text-brand-600 font-medium">
              {user.first_name?.charAt(0) || user.username.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <p className="font-medium text-slate-900">
              {user.first_name && user.last_name
                ? `${user.first_name} ${user.last_name}`
                : user.username}
              {isCurrentUser && (
                <span className="ml-2 px-2 py-0.5 text-xs bg-brand-100 text-brand-700 rounded">
                  Εσείς
                </span>
              )}
            </p>
            <p className="text-sm text-slate-500">@{user.username}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-slate-600">{user.email || '-'}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {user.is_superuser ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-purple-100 text-purple-700 rounded-full">
              <Shield size={12} />
              Διαχειριστής
            </span>
          ) : user.is_staff ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-brand-100 text-brand-700 rounded-full">
              <UserCheck size={12} />
              Προσωπικό
            </span>
          ) : (
            <span className="px-2 py-1 text-xs bg-slate-100 text-slate-600 rounded-full">
              Χρήστης
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        {user.is_active ? (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-success-100 text-success-700 rounded-full">
            <UserCheck size={12} />
            Ενεργός
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-danger-100 text-danger-700 rounded-full">
            <UserX size={12} />
            Ανενεργός
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-500">
        {formatDate(user.last_login)}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          {canEdit && !isCurrentUser && (
            <button
              onClick={handleToggleActive}
              disabled={toggleActive.isPending}
              className={`cursor-pointer p-1.5 rounded-lg transition-colors duration-150 ${
                user.is_active
                  ? 'hover:bg-orange-100 text-orange-600'
                  : 'hover:bg-success-100 text-success-600'
              }`}
              title={user.is_active ? 'Απενεργοποίηση' : 'Ενεργοποίηση'}
            >
              {user.is_active ? <UserX size={16} /> : <UserCheck size={16} />}
            </button>
          )}
          {canEdit && (
            <button
              onClick={onEdit}
              className="p-1.5 hover:bg-brand-100 text-brand-600 rounded-lg transition-colors duration-150 cursor-pointer"
              title="Επεξεργασία"
            >
              <Pencil size={16} />
            </button>
          )}
          {canEdit && !isCurrentUser && !user.is_superuser && (
            <button
              onClick={onDelete}
              className="p-1.5 hover:bg-danger-100 text-danger-600 rounded-lg transition-colors duration-150 cursor-pointer"
              title="Διαγραφή"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

// ============================================
// USER MODAL COMPONENT
// ============================================

interface UserModalProps {
  user: User | null;
  onClose: () => void;
  showToast: (type: 'success' | 'error' | 'info', message: string) => void;
}

function UserModal({ user, onClose, showToast }: UserModalProps) {
  const isEdit = !!user;
  const createMutation = useCreateUser();
  const updateMutation = useUpdateUser(user?.id || 0);

  const [formData, setFormData] = useState({
    username: user?.username || '',
    email: user?.email || '',
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    password: '',
    password_confirm: '',
    is_staff: user?.is_staff || false,
    is_active: user?.is_active ?? true,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const [previousUser, setPreviousUser] = useState(user);
  if (previousUser !== user) {
    setPreviousUser(user);
    setFormData({
      username: user?.username || '',
      email: user?.email || '',
      first_name: user?.first_name || '',
      last_name: user?.last_name || '',
      password: '',
      password_confirm: '',
      is_staff: user?.is_staff || false,
      is_active: user?.is_active ?? true,
    });
    setErrors({});
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    try {
      if (isEdit) {
        const updateData: UserUpdate = {
          username: formData.username,
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          is_staff: formData.is_staff,
          is_active: formData.is_active,
        };
        if (formData.password) {
          updateData.password = formData.password;
        }
        const result = await updateMutation.mutateAsync(updateData);
        showToast('success', result.message || 'Ο χρήστης ενημερώθηκε');
      } else {
        const createData: UserCreate = {
          username: formData.username,
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          password: formData.password,
          password_confirm: formData.password_confirm,
          is_staff: formData.is_staff,
          is_active: formData.is_active,
        };
        const result = await createMutation.mutateAsync(createData);
        showToast('success', result.message || 'Ο χρήστης δημιουργήθηκε');
      }
      onClose();
    } catch (error: unknown) {
      // Handle validation errors from backend
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { errors?: Record<string, string[]> } } };
        if (axiosError.response?.data?.errors) {
          setErrors(axiosError.response.data.errors);
        }
      }
      showToast('error', 'Σφάλμα κατά την αποθήκευση');
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="fixed inset-0 bg-black/50 transition-opacity"
          onClick={onClose}
        />

        <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg">
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900">
              {isEdit ? 'Επεξεργασία Χρήστη' : 'Νέος Χρήστης'}
            </h3>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
              {/* Username */}
              <div>
                <label htmlFor="user-management-f1" className="block text-sm font-medium text-slate-700 mb-1">
                  Όνομα χρήστη *
                </label>
                <input id="user-management-f1"
                  type="text"
                  value={formData.username}
                  onChange={(e) =>
                    setFormData({ ...formData, username: e.target.value })
                  }
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 ${
                    errors.username ? 'border-danger-600' : 'border-slate-200'
                  }`}
                  required
                />
                {errors.username && (
                  <p className="mt-1 text-sm text-danger-600">{errors.username[0]}</p>
                )}
              </div>

              {/* Email */}
              <div>
                <label htmlFor="user-management-f2" className="block text-sm font-medium text-slate-700 mb-1">
                  Email *
                </label>
                <input id="user-management-f2"
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 ${
                    errors.email ? 'border-danger-600' : 'border-slate-200'
                  }`}
                  required
                />
                {errors.email && (
                  <p className="mt-1 text-sm text-danger-600">{errors.email[0]}</p>
                )}
              </div>

              {/* First Name & Last Name */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="user-management-f3" className="block text-sm font-medium text-slate-700 mb-1">
                    Όνομα
                  </label>
                  <input id="user-management-f3"
                    type="text"
                    value={formData.first_name}
                    onChange={(e) =>
                      setFormData({ ...formData, first_name: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  />
                </div>
                <div>
                  <label htmlFor="user-management-f4" className="block text-sm font-medium text-slate-700 mb-1">
                    Επώνυμο
                  </label>
                  <input id="user-management-f4"
                    type="text"
                    value={formData.last_name}
                    onChange={(e) =>
                      setFormData({ ...formData, last_name: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Κωδικός {!isEdit && '*'}
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    className={`w-full px-3 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 ${
                      errors.password ? 'border-danger-600' : 'border-slate-200'
                    }`}
                    required={!isEdit}
                    placeholder={isEdit ? 'Αφήστε κενό για να μην αλλάξει' : ''}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 cursor-pointer transition-colors duration-150"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-sm text-danger-600">{errors.password[0]}</p>
                )}
              </div>

              {/* Password Confirm (only for create) */}
              {!isEdit && (
                <div>
                  <label htmlFor="user-management-f5" className="block text-sm font-medium text-slate-700 mb-1">
                    Επιβεβαίωση κωδικού *
                  </label>
                  <input id="user-management-f5"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password_confirm}
                    onChange={(e) =>
                      setFormData({ ...formData, password_confirm: e.target.value })
                    }
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 ${
                      errors.password_confirm ? 'border-danger-600' : 'border-slate-200'
                    }`}
                    required={!isEdit}
                  />
                  {errors.password_confirm && (
                    <p className="mt-1 text-sm text-danger-600">
                      {errors.password_confirm[0]}
                    </p>
                  )}
                </div>
              )}

              {/* Role Toggles */}
              <div className="space-y-3 pt-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_staff}
                    onChange={(e) =>
                      setFormData({ ...formData, is_staff: e.target.checked })
                    }
                    className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                  />
                  <div>
                    <span className="font-medium text-slate-900">Προσωπικό</span>
                    <p className="text-xs text-slate-500">
                      Πρόσβαση στο Django Admin
                    </p>
                  </div>
                </label>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) =>
                      setFormData({ ...formData, is_active: e.target.checked })
                    }
                    className="w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500"
                  />
                  <div>
                    <span className="font-medium text-slate-900">Ενεργός</span>
                    <p className="text-xs text-slate-500">
                      Μπορεί να συνδεθεί στο σύστημα
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={onClose}>
                Ακύρωση
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending ? (
                  <>
                    <RefreshCw size={18} className="animate-spin mr-2" />
                    Αποθήκευση...
                  </>
                ) : isEdit ? (
                  'Ενημέρωση'
                ) : (
                  'Δημιουργία'
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// ============================================
// DELETE DIALOG COMPONENT
// ============================================

interface DeleteUserDialogProps {
  user: User | null;
  onClose: () => void;
  showToast: (type: 'success' | 'error' | 'info', message: string) => void;
}

function DeleteUserDialog({ user, onClose, showToast }: DeleteUserDialogProps) {
  const deleteMutation = useDeleteUser();

  const handleConfirm = async () => {
    if (!user) return;

    try {
      const result = await deleteMutation.mutateAsync(user.id);
      showToast('success', result.message || 'Ο χρήστης διαγράφηκε');
      onClose();
    } catch (error: unknown) {
      const errMsg = error instanceof Error ? error.message : 'Σφάλμα διαγραφής';
      showToast('error', errMsg);
    }
  };

  return (
    <ConfirmDialog
      isOpen={!!user}
      onClose={onClose}
      onConfirm={handleConfirm}
      title="Διαγραφή Χρήστη"
      message={`Είστε σίγουροι ότι θέλετε να διαγράψετε τον χρήστη "${user?.username}"; Αυτή η ενέργεια δεν μπορεί να αναιρεθεί.`}
      isPending={deleteMutation.isPending}
    />
  );
}
