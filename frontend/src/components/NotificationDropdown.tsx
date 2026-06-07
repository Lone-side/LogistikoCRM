import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, AlertCircle, Clock, Calendar, X, RefreshCw } from 'lucide-react';
import { useNotifications, type Notification } from '../hooks/useNotifications';

export default function NotificationDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { data, isLoading, refetch, isRefetching } = useNotifications();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNotificationClick = (notification: Notification) => {
    setIsOpen(false);
    // Navigate to obligations page with client filter
    navigate(`/obligations?client=${notification.client_id}`);
  };

  const count = data?.count || 0;
  const notifications = data?.notifications || [];
  const overdueCount = data?.overdue_count || 0;
  const todayCount = data?.today_count || 0;

  const getIcon = (type: string) => {
    switch (type) {
      case 'overdue':
        return <AlertCircle size={16} className="text-red-500" />;
      case 'due_today':
        return <Clock size={16} className="text-orange-500" />;
      case 'upcoming':
        return <Calendar size={16} className="text-brand-500" />;
      default:
        return <Bell size={16} className="text-gray-500" />;
    }
  };

  const getPriorityClass = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'border-l-red-500 bg-red-50';
      case 'medium':
        return 'border-l-orange-500 bg-orange-50';
      default:
        return 'border-l-brand-500 bg-brand-50';
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 hover:bg-gray-100 rounded-lg transition-colors"
        aria-label="Ειδοποιήσεις"
      >
        <Bell size={20} className="text-gray-600" />
        {/* Notification badge - only show if there are notifications */}
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-lg border border-gray-200 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Ειδοποιήσεις</h3>
              <div className="flex gap-3 mt-1 text-xs text-gray-500">
                {overdueCount > 0 && (
                  <span className="text-red-600">{overdueCount} καθυστερημένες</span>
                )}
                {todayCount > 0 && (
                  <span className="text-orange-600">{todayCount} σήμερα</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetch()}
                className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                title="Ανανέωση"
                disabled={isRefetching}
              >
                <RefreshCw size={14} className={`text-gray-500 ${isRefetching ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                title="Κλείσιμο"
              >
                <X size={14} className="text-gray-500" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="max-h-[400px] overflow-y-auto">
            {isLoading ? (
              <div className="py-8 text-center text-gray-500">
                <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
                <span className="text-sm">Φόρτωση...</span>
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center text-gray-500">
                <Bell size={32} className="mx-auto mb-2 text-gray-300" />
                <p className="text-sm">Δεν υπάρχουν ειδοποιήσεις</p>
                <p className="text-xs text-gray-400 mt-1">Όλες οι υποχρεώσεις είναι ενημερωμένες!</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {notifications.map((notification) => (
                  <button
                    key={`${notification.type}-${notification.id}`}
                    onClick={() => handleNotificationClick(notification)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors border-l-4 ${getPriorityClass(notification.priority)}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">
                        {getIcon(notification.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {notification.title}
                        </p>
                        <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">
                          {notification.message}
                        </p>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-xs text-gray-400">
                            {notification.client_name}
                          </span>
                          <span className="text-xs text-gray-300">|</span>
                          <span className="text-xs text-gray-400">
                            {notification.deadline}
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
              <button
                onClick={() => {
                  setIsOpen(false);
                  navigate('/obligations?status=overdue,pending');
                }}
                className="w-full text-center text-sm text-brand-600 hover:text-brand-800 font-medium"
              >
                Προβολή όλων των υποχρεώσεων
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
