import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Menu,
  Moon,
  Search,
  Sun,
  User,
  LogOut,
  Settings,
  ChevronDown,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useTheme } from '../../hooks/useTheme';
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
  const { isDark, toggle: toggleTheme } = useTheme();

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
    <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 lg:px-6 shadow-sm">
      <div className="flex items-center justify-between h-full">
        {/* Left side */}
        <div className="flex items-center gap-4">
          {/* Mobile menu button */}
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            aria-label="Άνοιγμα μενού"
          >
            <Menu size={20} className="text-slate-600" />
          </button>

          {/* Search button */}
          <button
            onClick={onSearchClick}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-500 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer"
          >
            <Search size={18} />
            <span className="hidden sm:inline">Αναζήτηση...</span>
            <kbd className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-slate-400 bg-white border border-slate-200 rounded">
              <span>Ctrl</span>
              <span>K</span>
            </kbd>
          </button>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors duration-150 cursor-pointer"
            aria-label="Εναλλαγή θέματος"
            title="Εναλλαγή θέματος"
          >
            {isDark ? (
              <Sun size={20} className="text-slate-600" />
            ) : (
              <Moon size={20} className="text-slate-600" />
            )}
          </button>

          {/* Door Control Button */}
          <DoorButton />

          {/* Notifications */}
          <NotificationDropdown />

          {/* User dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-2 p-1.5 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              <div className="w-8 h-8 bg-gradient-to-br from-brand-600 to-brand-700 rounded-full flex items-center justify-center shadow-sm">
                <span className="text-white text-sm font-medium">{initials}</span>
              </div>
              <span className="hidden sm:inline text-sm font-medium text-slate-700">
                {displayName}
              </span>
              <ChevronDown
                size={16}
                className={`text-slate-400 transition-transform ${
                  isDropdownOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {/* Dropdown menu */}
            {isDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-slate-200 py-1 z-50">
                <div className="px-4 py-3 border-b border-slate-100">
                  <p className="text-sm font-medium text-slate-900">{displayName}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {user?.email || 'user@example.com'}
                  </p>
                </div>

                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    navigate('/settings');
                  }}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <User size={16} />
                  <span>Προφίλ</span>
                </button>

                <button
                  onClick={() => {
                    setIsDropdownOpen(false);
                    navigate('/settings');
                  }}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <Settings size={16} />
                  <span>Ρυθμίσεις</span>
                </button>

                <div className="border-t border-slate-100 mt-1 pt-1">
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 w-full px-4 py-2 text-sm text-danger-600 hover:bg-danger-50 transition-colors cursor-pointer"
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
