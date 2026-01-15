/**
 * filingSettings.ts
 * Types for Filing System Settings
 */

// Folder structure options
export type FolderStructure = 'standard' | 'year_first' | 'category_first' | 'flat' | 'custom';

// Folder creation mode (NEW)
export type FolderCreationMode = 'none' | 'minimal' | 'basic' | 'full';

// File naming conventions
export type FileNamingConvention = 'original' | 'structured' | 'date_prefix' | 'afm_prefix';

// Filing System Settings
export interface FilingSystemSettings {
  id: number;
  // Basic settings
  archive_root: string;
  archive_root_display: string;
  use_network_storage: boolean;
  // Auto folder creation (NEW)
  folder_creation_mode: FolderCreationMode;
  folder_templates: Record<string, any>;
  // Folder structure
  folder_structure: FolderStructure;
  custom_folder_template: string;
  use_greek_month_names: boolean;
  // Special folders
  enable_permanent_folder: boolean;
  permanent_folder_name: string;
  enable_yearend_folder: boolean;
  yearend_folder_name: string;
  // Categories
  document_categories: Record<string, string>;
  all_categories: Record<string, string>;
  permanent_categories: Record<string, string>;
  monthly_categories: Record<string, string>;
  yearend_categories: Record<string, string>;
  // File naming
  file_naming_convention: FileNamingConvention;
  // Retention policy
  retention_years: number;
  auto_archive_years: number;
  enable_retention_warnings: boolean;
  // Security
  allowed_extensions: string;
  max_file_size_mb: number;
  // Metadata
  created_at: string;
  updated_at: string;
}

// Folder creation mode choices (NEW)
export const FOLDER_CREATION_CHOICES: { value: FolderCreationMode; label: string; description: string }[] = [
  {
    value: 'none',
    label: 'Καμία',
    description: 'Χωρίς αυτόματη δημιουργία φακέλων'
  },
  {
    value: 'minimal',
    label: 'Ελάχιστη',
    description: 'Μόνο ο βασικός φάκελος πελάτη'
  },
  {
    value: 'basic',
    label: 'Βασική',
    description: 'Πελάτης + τρέχον έτος'
  },
  {
    value: 'full',
    label: 'Πλήρης',
    description: 'Μήνες, κατηγορίες, ετήσια'
  },
];

// Folder structure choices for dropdown
export const FOLDER_STRUCTURE_CHOICES: { value: FolderStructure; label: string; description: string }[] = [
  {
    value: 'standard',
    label: 'Τυπική',
    description: 'ΑΦΜ_Επωνυμία/Έτος/Μήνας/Κατηγορία'
  },
  {
    value: 'year_first',
    label: 'Πρώτα Έτος',
    description: 'Έτος/ΑΦΜ_Επωνυμία/Μήνας/Κατηγορία'
  },
  {
    value: 'category_first',
    label: 'Πρώτα Κατηγορία',
    description: 'Κατηγορία/ΑΦΜ_Επωνυμία/Έτος/Μήνας'
  },
  {
    value: 'flat',
    label: 'Επίπεδη',
    description: 'ΑΦΜ_Επωνυμία/Κατηγορία'
  },
  {
    value: 'custom',
    label: 'Προσαρμοσμένη',
    description: 'Δικό σας template'
  },
];

// File naming choices
export const FILE_NAMING_CHOICES: { value: FileNamingConvention; label: string; example: string }[] = [
  {
    value: 'original',
    label: 'Αρχικό όνομα',
    example: 'invoice.pdf'
  },
  {
    value: 'structured',
    label: 'Δομημένο',
    example: '20250115_123456789_vat_invoice.pdf'
  },
  {
    value: 'date_prefix',
    label: 'Ημ/νία + Αρχικό',
    example: '20250115_invoice.pdf'
  },
  {
    value: 'afm_prefix',
    label: 'ΑΦΜ + Αρχικό',
    example: '123456789_invoice.pdf'
  },
];

// Folder tree node
export interface FolderTreeNode {
  name: string;
  type: 'client' | 'permanent' | 'year' | 'month' | 'yearend' | 'category';
  client_id?: number;
  year?: number;
  month?: number;
  children?: FolderTreeNode[];
  document_count?: number;
  isExpanded?: boolean;
  isLoading?: boolean;
}

// Category with metadata
export interface CategoryMeta {
  value: string;
  label: string;
  icon: string;
  color: string;
  group: 'permanent' | 'monthly' | 'yearend';
}

// Grouped categories
export interface GroupedCategories {
  permanent: CategoryMeta[];
  monthly: CategoryMeta[];
  yearend: CategoryMeta[];
}

// Update request
export interface UpdateFilingSettingsRequest {
  use_network_storage?: boolean;
  archive_root?: string;
  // NEW
  folder_creation_mode?: FolderCreationMode;
  folder_templates?: Record<string, any>;
  // Existing
  folder_structure?: FolderStructure;
  custom_folder_template?: string;
  use_greek_month_names?: boolean;
  enable_permanent_folder?: boolean;
  permanent_folder_name?: string;
  enable_yearend_folder?: boolean;
  yearend_folder_name?: string;
  document_categories?: Record<string, string>;
  file_naming_convention?: FileNamingConvention;
  retention_years?: number;
  auto_archive_years?: number;
  enable_retention_warnings?: boolean;
  allowed_extensions?: string;
  max_file_size_mb?: number;
}
