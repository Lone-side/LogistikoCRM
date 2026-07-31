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

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: 'ΕΡΓΑΣΙΑ',
    items: [
      { to: '/', icon: <LayoutDashboard size={20} />, label: 'Πίνακας Ελέγχου' },
      { to: '/clients', icon: <Users size={20} />, label: 'Πελάτες' },
      { to: '/obligations', icon: <ClipboardList size={20} />, label: 'Υποχρεώσεις' },
      { to: '/calendar', icon: <Calendar size={20} />, label: 'Ημερολόγιο' },
      { to: '/file-manager', icon: <FolderOpen size={20} />, label: 'Αρχεία' },
    ],
  },
  {
    label: 'ΕΠΙΚΟΙΝΩΝΙΑ',
    items: [
      { to: '/calls', icon: <Phone size={20} />, label: 'Κλήσεις' },
      { to: '/tickets', icon: <Ticket size={20} />, label: 'Αιτήματα' },
      { to: '/emails', icon: <Mail size={20} />, label: 'Αλληλογραφία' },
    ],
  },
  {
    label: 'ΣΥΣΤΗΜΑ',
    items: [
      { to: '/mydata', icon: <FileText size={20} />, label: 'myDATA ΦΠΑ' },
      { to: '/reports', icon: <BarChart3 size={20} />, label: 'Αναφορές' },
      { to: '/settings', icon: <Settings size={20} />, label: 'Ρυθμίσεις' },
    ],
  },
];

export default function Sidebar({ isOpen, onClose, isCollapsed, onToggleCollapse }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-40 h-full flex flex-col
          bg-gradient-to-b from-[#020617] to-[#0c4a6e] text-[#cbd5e1]
          transform transition-all duration-300 ease-in-out
          lg:translate-x-0
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          ${isCollapsed ? 'w-16' : 'w-64'}
        `}
      >
        {/* Logo/Brand */}
        <div className={`flex items-center h-16 px-3 border-b border-white/10 ${isCollapsed ? 'justify-center' : 'justify-between px-4'}`}>
          {!isCollapsed && (
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 bg-gradient-to-br from-brand-600 to-brand-700 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand-950/40">
                <span className="text-white font-bold text-sm">LC</span>
              </div>
              <div className="min-w-0">
                <span className="block text-[15px] font-semibold text-white leading-tight truncate">LogistikoCRM</span>
                <span className="block text-[11px] text-slate-400 leading-tight truncate">Λογιστικό Γραφείο</span>
              </div>
            </div>
          )}
          {isCollapsed && (
            <div className="w-9 h-9 bg-gradient-to-br from-brand-600 to-brand-700 rounded-xl flex items-center justify-center shadow-lg shadow-brand-950/40">
              <span className="text-white font-bold text-sm">LC</span>
            </div>
          )}
          {/* Mobile close button - only show when not collapsed */}
          {!isCollapsed && (
            <button
              onClick={onClose}
              className="lg:hidden p-2 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
              aria-label="Κλείσιμο μενού"
            >
              <X size={20} className="text-slate-400" />
            </button>
          )}
        </div>

        {/* Collapse toggle button - desktop only */}
        <div className={`hidden lg:flex px-3 py-2 border-b border-white/10 ${isCollapsed ? 'justify-center' : 'justify-end'}`}>
          <button
            onClick={onToggleCollapse}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
            aria-label={isCollapsed ? 'Επέκταση μενού' : 'Σύμπτυξη μενού'}
            title={isCollapsed ? 'Επέκταση μενού' : 'Σύμπτυξη μενού'}
          >
            {isCollapsed ? (
              <ChevronRight size={18} className="text-slate-400" />
            ) : (
              <ChevronLeft size={18} className="text-slate-400" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-3 space-y-4 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label} className="space-y-0.5">
              {!isCollapsed ? (
                <p className="px-3 pb-1 text-[10px] font-semibold tracking-[0.14em] uppercase text-slate-500 select-none">
                  {group.label}
                </p>
              ) : (
                <div className="mx-3 mb-1 border-t border-white/10" aria-hidden="true" />
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onClose}
                  title={isCollapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    `group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-white/10 text-white shadow-lg shadow-brand-500/20'
                        : 'text-[#94a3b8] hover:bg-white/5 hover:text-[#f1f5f9]'
                    } ${isCollapsed ? 'justify-center' : ''}`
                  }
                  end={item.to === '/'}
                >
                  {({ isActive }) => (
                    <>
                      {/* Active indicator bar */}
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-brand-500 rounded-r-full" />
                      )}
                      <span className={`flex-shrink-0 transition-colors ${isActive ? 'text-brand-400' : 'text-slate-500 group-hover:text-[#cbd5e1]'}`}>
                        {item.icon}
                      </span>
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className={`p-3 border-t border-white/10 ${isCollapsed ? 'text-center' : ''}`}>
          <div className="text-xs text-slate-500 text-center truncate">
            {isCollapsed ? 'v1.0' : 'LogistikoCRM v1.0'}
          </div>
        </div>
      </aside>
    </>
  );
}
