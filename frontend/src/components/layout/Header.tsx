import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Menu,
  Search,
  User,
  LogOut,
  Settings,
  ChevronDown,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import DoorButton from '../DoorButton';
import NotificationDropdown from '../NotificationDropdown';

interface HeaderProps {
  onMenuClick: () => void;
  onSearchClick: () => void;
}

export default function Header({ onMenuClick, onSearchClick }: HeaderProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const displayName = user?.first_name || user?.username || 'Χρήστης';
  const initials = displayName.charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-gray-200 px-4 lg:px-6 shadow-sm">
      <div className="flex items-center justify-between h-full">
        {/* Left side */}
        <div className="flex items-center gap-4">
          {/* Mobile menu button */}
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Άνοιγμα μενού"
          >
            <Menu size={20} className="text-gray-600" />
          </button>

          {/* Search button */}
          <button
            onClick={onSearchClick}
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-500 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <Search size={18} />
            <span className="hidden sm:inline">Αναζήτηση...</span>
            <kbd className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-gray-400 bg-white border border-gray-200 rounded">
              <span>Ctrl</span>
              <span>K</span>
            </kbd>
          </button>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Door Control Button */}
          <DoorButton />

          {/* Notifications */}
          <NotificationDropdown />

          {/* User dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-2 p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-sm">
                <span className="text-white text-sm font-medium">{initials}</span>
              </div>
              <span className="hidden sm:inline text-sm font-medium text-gray-700">
                {displayName}
              </span>
              <ChevronDown
                size={16}
                className={`text-gray-400 transition-transform ${
                  isDropdownOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {/* Dropdown menu */}
            {isDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">{displayName}</p>
                  <p className="text-xs text-gray-500 truncate">
                    {user?.email || 'user@example.com'}
                  </p>
                </div>

                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    navigate('/settings');
                  }}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <User size={16} />
                  <span>Προφίλ</span>
                </button>

                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    navigate('/settings');
                  }}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <Settings size={16} />
                  <span>Ρυθμίσεις</span>
                </button>

                <div className="border-t border-gray-100 mt-1 pt-1">
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut size={16} />
                    <span>Αποσύνδεση</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
