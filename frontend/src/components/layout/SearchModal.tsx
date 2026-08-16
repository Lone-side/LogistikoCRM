import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Users,
  ClipboardList,
  Ticket,
  Phone,
  X,
  Loader2
} from 'lucide-react';
import { useGlobalSearch, type SearchResultItem } from '../../hooks/useGlobalSearch';
import {
  OBLIGATION_STATUS_COLORS,
  TICKET_STATUS_COLORS,
  CALL_STATUS_BADGE_COLORS as CALL_STATUS_COLORS,
} from '../../constants';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Category configuration with icons and labels
const CATEGORIES = {
  clients: {
    label: 'ΠΕΛΑΤΕΣ',
    icon: Users,
    iconBg: 'bg-brand-100',
    iconColor: 'text-brand-700'
  },
  obligations: {
    label: 'ΥΠΟΧΡΕΩΣΕΙΣ',
    icon: ClipboardList,
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600'
  },
  tickets: {
    label: 'TICKETS',
    icon: Ticket,
    iconBg: 'bg-orange-100',
    iconColor: 'text-orange-600'
  },
  calls: {
    label: 'ΚΛΗΣΕΙΣ',
    icon: Phone,
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600'
  }
} as const;

type CategoryKey = keyof typeof CATEGORIES;

export default function SearchModal({ isOpen, onClose }: SearchModalProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Use the new unified search hook
  const { data: searchData, isLoading } = useGlobalSearch(query, isOpen);

  // Flatten results for keyboard navigation
  const flatResults = useMemo(() => {
    if (!searchData?.results) return [];

    const items: Array<{ category: CategoryKey; item: SearchResultItem }> = [];

    const categories: CategoryKey[] = ['clients', 'obligations', 'tickets', 'calls'];
    categories.forEach((category) => {
      const categoryItems = searchData.results[category] || [];
      categoryItems.forEach((item) => {
        items.push({ category, item });
      });
    });

    return items;
  }, [searchData]);

  const [wasOpen, setWasOpen] = useState(isOpen);
  if (wasOpen !== isOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
    }
  }

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => inputRef.current?.focus(), 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Scroll selected item into view
  useEffect(() => {
    if (resultsContainerRef.current && flatResults.length > 0) {
      const selectedElement = resultsContainerRef.current.querySelector(
        `[data-index="${selectedIndex}"]`
      );
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex, flatResults.length]);

  // Navigate to result
  const navigateToResult = useCallback(
    (result: SearchResultItem) => {
      navigate(result.url);
      onClose();
    },
    [navigate, onClose]
  );

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => Math.min(prev + 1, flatResults.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (flatResults[selectedIndex]) {
            navigateToResult(flatResults[selectedIndex].item);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, flatResults, selectedIndex, navigateToResult, onClose]);

  // Get status badge for different item types
  const getStatusBadge = (item: SearchResultItem) => {
    const extra = item.extra as Record<string, string> | undefined;
    if (!extra?.status) return null;

    let colorClass = 'bg-slate-100 text-slate-700';
    const statusText = extra.status_display || extra.status;

    if (item.type === 'obligation') {
      colorClass = OBLIGATION_STATUS_COLORS[extra.status] || colorClass;
    } else if (item.type === 'ticket') {
      colorClass = TICKET_STATUS_COLORS[extra.status] || colorClass;
    } else if (item.type === 'call') {
      colorClass = CALL_STATUS_COLORS[extra.status] || colorClass;
    }

    return (
      <span className={`px-2 py-0.5 text-xs rounded-full whitespace-nowrap ${colorClass}`}>
        {statusText}
      </span>
    );
  };

  // Render a single result item
  const renderResultItem = (
    item: SearchResultItem,
    category: CategoryKey,
    globalIndex: number
  ) => {
    const config = CATEGORIES[category];
    const Icon = config.icon;
    const isSelected = selectedIndex === globalIndex;

    return (
      <button
        key={`${item.type}-${item.id}`}
        data-index={globalIndex}
        onClick={() => navigateToResult(item)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer ${
          isSelected ? 'bg-brand-50' : 'hover:bg-slate-50'
        }`}
      >
        <div
          className={`w-10 h-10 ${config.iconBg} rounded-full flex items-center justify-center flex-shrink-0`}
        >
          <Icon size={18} className={config.iconColor} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-slate-900 truncate">{item.title}</p>
          <p className="text-sm text-slate-500 truncate">{item.subtitle}</p>
        </div>
        {getStatusBadge(item)}
      </button>
    );
  };

  // Render a category section
  const renderCategory = (category: CategoryKey, startIndex: number) => {
    const items = searchData?.results[category] || [];
    if (items.length === 0) return { element: null, nextIndex: startIndex };

    const config = CATEGORIES[category];

    const element = (
      <div key={category}>
        <div className="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider border-t border-slate-100 first:border-t-0">
          {config.label}
        </div>
        {items.map((item, idx) => renderResultItem(item, category, startIndex + idx))}
      </div>
    );

    return { element, nextIndex: startIndex + items.length };
  };

  // Render all category sections
  const renderAllCategories = () => {
    let currentIndex = 0;
    const elements: React.ReactNode[] = [];

    const categories: CategoryKey[] = ['clients', 'obligations', 'tickets', 'calls'];
    categories.forEach((category) => {
      const { element, nextIndex } = renderCategory(category, currentIndex);
      if (element) {
        elements.push(element);
      }
      currentIndex = nextIndex;
    });

    return elements;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop ως ξεχωριστός, κρυμμένος από τον a11y tree κόμβος — όπως
          στο components/Modal.tsx. Το κλείσιμο με πληκτρολόγιο γίνεται με
          Escape (listener παραπάνω). */}
      <div
        aria-hidden="true"
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
      />

      <div className="relative z-10 w-full max-w-2xl bg-white rounded-xl shadow-2xl overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200">
          <Search size={20} className="text-slate-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Αναζήτηση πελατών, υποχρεώσεων, tickets, κλήσεων..."
            className="flex-1 text-lg outline-none placeholder-slate-400"
          />
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
          >
            <X size={18} className="text-slate-400" />
          </button>
        </div>

        {/* Results */}
        <div ref={resultsContainerRef} className="max-h-[60vh] overflow-y-auto">
          {query.length < 2 ? (
            <div className="px-4 py-8 text-center text-slate-500">
              <Search size={40} className="mx-auto mb-2 opacity-50" />
              <p>Πληκτρολογήστε τουλάχιστον 2 χαρακτήρες</p>
              <p className="text-sm text-slate-400 mt-1">
                Αναζήτηση με επωνυμία, ΑΦΜ, τηλέφωνο ή τύπο
              </p>
            </div>
          ) : isLoading ? (
            <div className="px-4 py-8 text-center text-slate-500">
              <Loader2 size={24} className="mx-auto mb-2 animate-spin" />
              <p>Αναζήτηση...</p>
            </div>
          ) : flatResults.length === 0 ? (
            <div className="px-4 py-8 text-center text-slate-500">
              <p>Δεν βρέθηκαν αποτελέσματα για "{query}"</p>
            </div>
          ) : (
            <div className="py-2">{renderAllCategories()}</div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">
                  ↑↓
                </kbd>
                <span>Πλοήγηση</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">
                  Enter
                </kbd>
                <span>Επιλογή</span>
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px]">
                  Esc
                </kbd>
                <span>Κλείσιμο</span>
              </span>
            </div>
            {searchData && searchData.total > 0 && (
              <span className="text-slate-400">
                {searchData.total} αποτελέσματα
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
