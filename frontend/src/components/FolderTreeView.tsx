/**
 * FolderTreeView.tsx
 * Hierarchical folder browser component for file manager
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Building2,
  Calendar,
  CalendarDays,
  FileText,
  Star,
  Users,
  Percent,
  Wallet,
  FileOutput,
  FileInput,
  Landmark,
  Receipt,
  Home,
  BarChart3,
  Scale,
  ClipboardCheck,
  BadgeCheck,
  Mail,
  FileSignature,
} from 'lucide-react';
import type { FolderTreeNode, CategoryMeta } from '../types/filingSettings';

// ============================================
// ICON MAPPING
// ============================================

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  registration: <Building2 className="w-4 h-4" />,
  contracts: <FileSignature className="w-4 h-4" />,
  licenses: <BadgeCheck className="w-4 h-4" />,
  correspondence: <Mail className="w-4 h-4" />,
  vat: <Percent className="w-4 h-4" />,
  apd: <Users className="w-4 h-4" />,
  myf: <FileText className="w-4 h-4" />,
  payroll: <Wallet className="w-4 h-4" />,
  invoices_issued: <FileOutput className="w-4 h-4" />,
  invoices_received: <FileInput className="w-4 h-4" />,
  bank: <Landmark className="w-4 h-4" />,
  receipts: <Receipt className="w-4 h-4" />,
  e1: <FileText className="w-4 h-4" />,
  e2: <Home className="w-4 h-4" />,
  e3: <BarChart3 className="w-4 h-4" />,
  enfia: <Building2 className="w-4 h-4" />,
  balance: <Scale className="w-4 h-4" />,
  audit: <ClipboardCheck className="w-4 h-4" />,
  general: <Folder className="w-4 h-4" />,
};

const CATEGORY_COLORS: Record<string, string> = {
  registration: '#8B5CF6',
  contracts: '#A855F7',
  licenses: '#9333EA',
  correspondence: '#7C3AED',
  vat: '#EF4444',
  apd: '#6366F1',
  myf: '#3B82F6',
  payroll: '#EC4899',
  invoices_issued: '#10B981',
  invoices_received: '#14B8A6',
  bank: '#0EA5E9',
  receipts: '#22C55E',
  e1: '#F59E0B',
  e2: '#F97316',
  e3: '#FB923C',
  enfia: '#FBBF24',
  balance: '#FCD34D',
  audit: '#FDE047',
  general: '#6B7280',
};

// ============================================
// TREE NODE COMPONENT
// ============================================

interface TreeNodeProps {
  node: FolderTreeNode;
  level: number;
  onSelect?: (node: FolderTreeNode, path: string[]) => void;
  selectedPath?: string[];
  path?: string[];
}

const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  level,
  onSelect,
  selectedPath = [],
  path = [],
}) => {
  const [isExpanded, setIsExpanded] = useState(level < 2);
  const hasChildren = node.children && node.children.length > 0;
  const currentPath = [...path, node.name];
  const isSelected = selectedPath.join('/') === currentPath.join('/');

  const getIcon = () => {
    switch (node.type) {
      case 'client':
        return <Building2 className="w-4 h-4 text-blue-600" />;
      case 'permanent':
        return <Star className="w-4 h-4 text-purple-500" />;
      case 'year':
        return <Calendar className="w-4 h-4 text-green-600" />;
      case 'month':
        return <CalendarDays className="w-4 h-4 text-cyan-600" />;
      case 'yearend':
        return <FileText className="w-4 h-4 text-amber-500" />;
      case 'category':
        const icon = CATEGORY_ICONS[node.name];
        const color = CATEGORY_COLORS[node.name] || '#6B7280';
        return icon ? (
          <span style={{ color }}>{icon}</span>
        ) : (
          <Folder className="w-4 h-4 text-gray-500" />
        );
      default:
        return isExpanded ? (
          <FolderOpen className="w-4 h-4 text-amber-500" />
        ) : (
          <Folder className="w-4 h-4 text-amber-500" />
        );
    }
  };

  const handleClick = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
    if (onSelect) {
      onSelect(node, currentPath);
    }
  };

  return (
    <div className="select-none">
      <div
        className={`flex items-center py-1 px-2 rounded cursor-pointer transition-colors ${
          isSelected
            ? 'bg-blue-100 dark:bg-blue-900/30'
            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
      >
        {/* Expand/Collapse Icon */}
        <span className="w-4 h-4 mr-1 flex items-center justify-center">
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )
          ) : (
            <span className="w-4" />
          )}
        </span>

        {/* Folder Icon */}
        <span className="mr-2">{getIcon()}</span>

        {/* Name */}
        <span className="text-sm truncate flex-1">{node.name}</span>

        {/* Document Count */}
        {node.document_count !== undefined && node.document_count > 0 && (
          <span className="text-xs text-gray-400 ml-2">
            ({node.document_count})
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child, index) => (
            <TreeNode
              key={`${child.name}-${index}`}
              node={child}
              level={level + 1}
              onSelect={onSelect}
              selectedPath={selectedPath}
              path={currentPath}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================
// FOLDER TREE VIEW COMPONENT
// ============================================

interface FolderTreeViewProps {
  structure: FolderTreeNode | null;
  onSelect?: (node: FolderTreeNode, path: string[]) => void;
  selectedPath?: string[];
  className?: string;
  loading?: boolean;
}

const FolderTreeView: React.FC<FolderTreeViewProps> = ({
  structure,
  onSelect,
  selectedPath = [],
  className = '',
  loading = false,
}) => {
  if (loading) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="animate-pulse space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center space-x-2">
              <div className="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="w-4 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
              <div
                className="h-4 bg-gray-200 dark:bg-gray-700 rounded"
                style={{ width: `${100 - i * 10}px` }}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!structure) {
    return (
      <div className={`p-4 text-center text-gray-500 ${className}`}>
        <Folder className="w-12 h-12 mx-auto mb-2 text-gray-300" />
        <p>Δεν υπάρχει δομή φακέλων</p>
      </div>
    );
  }

  return (
    <div className={`py-2 ${className}`}>
      <TreeNode
        node={structure}
        level={0}
        onSelect={onSelect}
        selectedPath={selectedPath}
      />
    </div>
  );
};

export default FolderTreeView;

// ============================================
// MINI TREE PREVIEW (for settings)
// ============================================

interface MiniTreePreviewProps {
  structure: FolderTreeNode | null;
  maxHeight?: string;
}

export const MiniTreePreview: React.FC<MiniTreePreviewProps> = ({
  structure,
  maxHeight = '300px',
}) => {
  if (!structure) {
    return (
      <div className="border rounded-lg p-4 bg-gray-50 dark:bg-gray-800">
        <p className="text-gray-500 text-sm">Φόρτωση προεπισκόπησης...</p>
      </div>
    );
  }

  return (
    <div
      className="border rounded-lg bg-gray-50 dark:bg-gray-800 overflow-auto"
      style={{ maxHeight }}
    >
      <div className="p-2 border-b bg-white dark:bg-gray-900">
        <span className="text-xs font-medium text-gray-500">
          Προεπισκόπηση Δομής Φακέλων
        </span>
      </div>
      <FolderTreeView structure={structure} />
    </div>
  );
};
