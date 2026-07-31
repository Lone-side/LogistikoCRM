import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  path?: string;
}

// Route label mapping
const routeLabels: Record<string, string> = {
  '': 'Dashboard',
  'dashboard': 'Dashboard',
  'clients': 'Πελάτες',
  'obligations': 'Υποχρεώσεις',
  'files': 'Αρχεία',
  'calls': 'Κλήσεις',
  'emails': 'Email',
  'reports': 'Αναφορές',
  'settings': 'Ρυθμίσεις',
  'new': 'Νέο',
  'edit': 'Επεξεργασία',
};

export default function Breadcrumbs() {
  const location = useLocation();
  const pathSegments = location.pathname.split('/').filter(Boolean);

  // Don't show breadcrumbs on dashboard
  if (pathSegments.length === 0 || pathSegments[0] === 'dashboard') {
    return null;
  }

  // Build breadcrumb items
  const breadcrumbs: BreadcrumbItem[] = [];
  let currentPath = '';

  for (let i = 0; i < pathSegments.length; i++) {
    const segment = pathSegments[i];
    currentPath += `/${segment}`;

    // Check if it's a numeric ID
    const isId = /^\d+$/.test(segment);
    const label = isId ? `#${segment}` : (routeLabels[segment] || segment);

    breadcrumbs.push({
      label,
      path: i < pathSegments.length - 1 ? currentPath : undefined,
    });
  }

  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="flex items-center gap-1 text-sm">
        {/* Home link */}
        <li>
          <Link
            to="/"
            className="flex items-center gap-1 text-slate-500 hover:text-slate-700 transition-colors"
          >
            <Home size={14} />
            <span className="sr-only">Αρχική</span>
          </Link>
        </li>

        {breadcrumbs.map((item, index) => (
          <li key={index} className="flex items-center gap-1">
            <ChevronRight size={14} className="text-slate-400" />
            {item.path ? (
              <Link
                to={item.path}
                className="text-slate-500 hover:text-slate-700 transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span className="text-slate-900 font-medium">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
