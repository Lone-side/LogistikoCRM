import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  Calendar,
  FolderOpen,
  Phone,
  Ticket,
  Mail,
  BarChart3,
  Settings,
  X,
  ChevronLeft,
  ChevronRight,
  FileText,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/', icon: <LayoutDashboard size={20} />, label: 'Πίνακας Ελέγχου' },
  { to: '/clients', icon: <Users size={20} />, label: 'Πελάτες' },
  { to: '/obligations', icon: <ClipboardList size={20} />, label: 'Υποχρεώσεις' },
  { to: '/calendar', icon: <Calendar size={20} />, label: 'Ημερολόγιο' },
  { to: '/file-manager', icon: <FolderOpen size={20} />, label: 'Αρχεία' },
  { to: '/calls', icon: <Phone size={20} />, label: 'Κλήσεις' },
  { to: '/tickets', icon: <Ticket size={20} />, label: 'Αιτήματα' },
  { to: '/emails', icon: <Mail size={20} />, label: 'Αλληλογραφία' },
  { to: '/mydata', icon: <FileText size={20} />, label: 'myDATA ΦΠΑ' },
  { to: '/reports', icon: <BarChart3 size={20} />, label: 'Αναφορές' },
  { to: '/settings', icon: <Settings size={20} />, label: 'Ρυθμίσεις' },
];

export default function Sidebar({ isOpen, onClose, isCollapsed, onToggleCollapse }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-40 h-full bg-white border-r border-gray-200
          transform transition-all duration-300 ease-in-out
          lg:translate-x-0
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          ${isCollapsed ? 'w-16' : 'w-64'}
        `}
      >
        {/* Logo/Brand */}
        <div className={`flex items-center h-16 px-3 border-b border-gray-200 ${isCollapsed ? 'justify-center' : 'justify-between px-4'}`}>
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <span className="text-white font-bold text-sm">LC</span>
              </div>
              <span className="text-lg font-semibold text-gray-900 truncate">LogistikoCRM</span>
            </div>
          )}
          {isCollapsed && (
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">LC</span>
            </div>
          )}
          {/* Mobile close button - only show when not collapsed */}
          {!isCollapsed && (
            <button
              onClick={onClose}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Κλείσιμο μενού"
            >
              <X size={20} className="text-gray-500" />
            </button>
          )}
        </div>

        {/* Collapse toggle button - desktop only */}
        <div className={`hidden lg:flex px-3 py-2 border-b border-gray-200 ${isCollapsed ? 'justify-center' : 'justify-end'}`}>
          <button
            onClick={onToggleCollapse}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label={isCollapsed ? 'Επέκταση μενού' : 'Σύμπτυξη μενού'}
            title={isCollapsed ? 'Επέκταση μενού' : 'Σύμπτυξη μενού'}
          >
            {isCollapsed ? (
              <ChevronRight size={18} className="text-gray-500" />
            ) : (
              <ChevronLeft size={18} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              title={isCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                } ${isCollapsed ? 'justify-center' : ''}`
              }
              end={item.to === '/'}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!isCollapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className={`p-3 border-t border-gray-200 ${isCollapsed ? 'text-center' : ''}`}>
          <div className="text-xs text-gray-400 text-center truncate">
            {isCollapsed ? 'v1.0' : 'LogistikoCRM v1.0'}
          </div>
        </div>
      </aside>
    </>
  );
}
