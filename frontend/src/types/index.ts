// User types
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser?: boolean;
}

// Client/Customer types (ClientProfile in Django)
// Fields match accounting/serializers.py ClientSerializer
export interface Client {
  id: number;
  afm: string;                      // ΑΦΜ - Greek Tax ID (9 digits)
  eponimia: string;                 // Επωνυμία - Company name
  email?: string | null;
  kinito_tilefono?: string | null;  // Κινητό τηλέφωνο
  tilefono_oikias_1?: string | null;
  tilefono_oikias_2?: string | null;
  tilefono_epixeirisis_1?: string | null;
  tilefono_epixeirisis_2?: string | null;
  total_obligations?: number;
  is_active?: boolean;
  eidos_ipoxreou?: 'individual' | 'professional' | 'company' | null;  // Είδος υπόχρεου
  // GSIS fields
  doy?: string | null;
  nomiki_morfi?: string | null;
  diefthinsi_epixeirisis?: string | null;
  arithmos_epixeirisis?: string | null;
  poli_epixeirisis?: string | null;
  tk_epixeirisis?: string | null;
  imerominia_enarksis?: string | null;
}

// Obligation status types
export type ObligationStatus =
  | 'pending'      // Εκκρεμεί
  | 'in_progress'  // Σε εξέλιξη
  | 'completed'    // Ολοκληρώθηκε
  | 'overdue'      // Εκπρόθεσμη
  | 'cancelled';   // Ακυρώθηκε

// Obligation type codes
export type ObligationType =
  | 'ΦΠΑ'    // Φόρος Προστιθέμενης Αξίας
  | 'ΑΠΔ'    // Αναλυτική Περιοδική Δήλωση ΕΦΚΑ
  | 'ΕΝΦΙΑ'  // Ενιαίος Φόρος Ιδιοκτησίας
  | 'Ε1'     // Δήλωση Φορολογίας Εισοδήματος
  | 'Ε3'     // Κατάσταση Οικονομικών Στοιχείων
  | 'ΜΥΦ'    // Συγκεντρωτικές Καταστάσεις
  | string;  // Allow custom types

// Monthly Obligation type
// Fields match accounting/serializers.py MonthlyObligationSerializer
export interface Obligation {
  id: number;
  client: number;               // Foreign key to Client
  client_name?: string;         // from client.eponimia (read_only)
  obligation_type: number;      // Foreign key to ObligationType
  type_name?: string;           // from obligation_type.name (read_only)
  type_code?: string;           // from obligation_type.code (read_only)
  month: number;                // 1-12
  year: number;
  deadline: string;             // ISO date string
  status: ObligationStatus;
  completed_date?: string | null;
  completed_by?: number | null;
  assigned_to?: number | null;  // Foreign key to User
  assigned_to_name?: string | null;  // from assigned_to.username or full name (read_only)
  notes?: string;
  time_spent?: number | null;
  hourly_rate?: number | null;
  attachment?: string | null;
  attachments?: string[];
  documents_count?: number;     // Count of attached documents (read_only)
  created_at: string;
  updated_at: string;
}

// Ticket types
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Ticket {
  id: number;
  client: number;
  client_name?: string;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  assigned_to?: number;
  assigned_to_name?: string;
  created_at: string;
  updated_at: string;
}

// API response types
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  detail?: string;
  message?: string;
  [key: string]: unknown;
}

// Auth types
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

// Form types for creating/updating
export interface ClientFormData {
  afm: string;
  eponimia: string;
  eidos_ipoxreou: 'individual' | 'professional' | 'company';
  email?: string;
  kinito_tilefono?: string;
  tilefono_oikias_1?: string;
  tilefono_epixeirisis_1?: string;
  is_active?: boolean;
  // GSIS fields
  doy?: string;
  nomiki_morfi?: string;
  diefthinsi_epixeirisis?: string;
  arithmos_epixeirisis?: string;
  poli_epixeirisis?: string;
  tk_epixeirisis?: string;
  // null: το Django DateField θέλει null αντί για κενό string
  imerominia_enarksis?: string | null;
}

export interface ObligationFormData {
  client: number;
  obligation_type: number;  // FK to ObligationType
  month: number;
  year: number;
  deadline: string;
  status?: ObligationStatus;
  completed_date?: string | null;
  time_spent?: number | null;
  notes?: string;
  assigned_to?: number | null;  // FK to User
}

// Dashboard statistics
export interface DashboardStats {
  total_clients: number;
  active_clients: number;
  pending_obligations: number;
  overdue_obligations: number;
  completed_this_month: number;
}

// Obligation Type from API
export interface ObligationTypeData {
  id: number;
  code: string;
  name: string;
  frequency: 'monthly' | 'quarterly' | 'annual' | 'follows_vat';
  deadline_type: 'last_day' | 'specific_day' | 'last_day_prev' | 'last_day_next';
  deadline_day: number | null;
}

// Bulk creation form data
export interface BulkObligationFormData {
  client_ids: number[];
  obligation_type: number;
  month: number;
  year: number;
}

// Bulk update form data
export interface BulkUpdateFormData {
  obligation_ids: number[];
  status: ObligationStatus;
}

// ============================================
// CLIENT DETAILS TYPES
// ============================================

// Full client interface with all fields
export interface ClientFull {
  id: number;
  // Basic info
  afm: string;
  doy?: string | null;
  eponimia: string;
  onoma?: string | null;
  onoma_patros?: string | null;
  // Identity
  arithmos_taftotitas?: string | null;
  eidos_taftotitas?: string | null;
  prosopikos_arithmos?: string | null;
  amka?: string | null;
  am_ika?: string | null;
  arithmos_gemi?: string | null;
  arithmos_dypa?: string | null;
  // Personal dates
  imerominia_gennisis?: string | null;
  imerominia_gamou?: string | null;
  filo?: 'M' | 'F' | null;
  // Home address
  diefthinsi_katoikias?: string | null;
  arithmos_katoikias?: string | null;
  poli_katoikias?: string | null;
  dimos_katoikias?: string | null;
  nomos_katoikias?: string | null;
  tk_katoikias?: string | null;
  tilefono_oikias_1?: string | null;
  tilefono_oikias_2?: string | null;
  kinito_tilefono?: string | null;
  // Business address
  diefthinsi_epixeirisis?: string | null;
  arithmos_epixeirisis?: string | null;
  poli_epixeirisis?: string | null;
  dimos_epixeirisis?: string | null;
  nomos_epixeirisis?: string | null;
  tk_epixeirisis?: string | null;
  tilefono_epixeirisis_1?: string | null;
  tilefono_epixeirisis_2?: string | null;
  email?: string | null;
  // Bank info
  trapeza?: string | null;
  iban?: string | null;
  // Tax info
  eidos_ipoxreou: 'individual' | 'professional' | 'company';
  katigoria_vivlion?: 'A' | 'B' | 'C' | 'none' | null;
  nomiki_morfi?: string | null;
  agrotis?: boolean;
  imerominia_enarksis?: string | null;
  // Credentials
  onoma_xristi_taxisnet?: string | null;
  kodikos_taxisnet?: string | null;
  onoma_xristi_ika_ergodoti?: string | null;
  kodikos_ika_ergodoti?: string | null;
  onoma_xristi_gemi?: string | null;
  kodikos_gemi?: string | null;
  // Related
  afm_sizigou?: string | null;
  afm_foreas?: string | null;
  am_klidi?: string | null;
  // Meta
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Computed counts
  obligations_count?: number;
  documents_count?: number;
  pending_obligations_count?: number;
  // Extended counts from /full endpoint
  counts?: {
    obligations: number;
    pending_obligations: number;
    overdue_obligations: number;
    documents: number;
    emails: number;
    calls: number;
    tickets: number;
    open_tickets: number;
  };
}

// Client Document interface
export interface ClientDocument {
  id: number;
  client: number;
  client_name?: string;
  obligation?: number | null;
  obligation_type?: string | null;
  file: string;
  file_url?: string | null;
  filename: string;
  original_filename?: string;
  file_type: string;
  file_size?: number;
  file_size_display?: string;
  document_category: 'contracts' | 'invoices' | 'tax' | 'myf' | 'vat' | 'payroll' | 'general';
  category_display?: string;
  description?: string;
  uploaded_at: string;
  // Versioning fields
  version?: number;
  is_current?: boolean;
  year?: number;
  month?: number;
  uploaded_by?: string | null;
}

// Document Categories
export const DOCUMENT_CATEGORIES = [
  { value: 'contract', label: 'Σύμβαση' },
  { value: 'invoice', label: 'Τιμολόγιο' },
  { value: 'tax_return', label: 'Φορολογική Δήλωση' },
  { value: 'vat', label: 'ΦΠΑ' },
  { value: 'payroll', label: 'Μισθοδοσία' },
  { value: 'apd', label: 'ΑΠΔ' },
  { value: 'other', label: 'Άλλο' },
];

// Email Log interface
export interface EmailLog {
  id: number;
  recipient_email: string;
  recipient_name: string;
  client: number | null;
  client_name?: string;
  client_afm?: string;
  obligation: number | null;
  obligation_type?: string;
  template_used: number | null;
  template_name?: string | null;
  subject: string;
  body?: string;
  status: 'sent' | 'failed' | 'pending' | 'queued';
  status_display?: string;
  error_message?: string;
  sent_at: string | null;
  sent_by?: number | null;
  sent_by_name?: string;
}

// VoIP Call interface
export interface VoIPCall {
  id: number;
  call_id: string;
  phone_number: string;
  direction: 'incoming' | 'outgoing';
  direction_display?: string;
  status: 'active' | 'completed' | 'missed' | 'failed';
  status_display?: string;
  started_at: string | null;
  ended_at?: string | null;
  duration_seconds: number;
  duration_formatted?: string;
  notes?: string;
  resolution?: 'pending' | 'closed' | 'follow_up';
  ticket_created?: boolean;
}

// VoIP Call Full interface (with nested client)
export interface VoIPCallFull {
  id: number;
  call_id: string;
  phone_number: string;
  direction: 'incoming' | 'outgoing';
  direction_display?: string;
  status: 'active' | 'completed' | 'missed' | 'failed';
  status_display?: string;
  duration_seconds: number;
  duration_formatted?: string;
  started_at: string;
  ended_at?: string | null;
  client?: {
    id: number;
    eponimia: string;
    afm: string;
  } | null;
  has_ticket: boolean;
  notes?: string;
  resolution?: 'pending' | 'closed' | 'follow_up';
  created_at: string;
  updated_at: string;
}

// VoIP Ticket interface (extended from base Ticket)
export interface VoIPTicket {
  id: number;
  title: string;
  description?: string;
  status: 'open' | 'assigned' | 'in_progress' | 'resolved' | 'closed';
  status_display?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  priority_display?: string;
  assigned_to?: number | null;
  assigned_to_name?: string | null;
  created_at: string;
  resolved_at?: string | null;
  is_open: boolean;
  days_since_created: number;
}

// Ticket Full interface (with nested client and call)
export interface TicketFull {
  id: number;
  title: string;
  description?: string;
  status: 'open' | 'assigned' | 'in_progress' | 'resolved' | 'closed';
  status_display?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  priority_display?: string;
  client?: {
    id: number;
    eponimia: string;
    afm: string;
  } | null;
  call?: {
    id: number;
    phone_number: string;
    direction: string;
    direction_display?: string;
    started_at?: string;
  } | null;
  assigned_to?: number | null;
  assigned_to_name?: string | null;
  notes?: string;
  created_at: string;
  assigned_at?: string | null;
  resolved_at?: string | null;
  closed_at?: string | null;
  days_since_created: number;
  is_open: boolean;
}

// Calls Stats
export interface CallsStats {
  total: number;
  incoming: number;
  outgoing: number;
  missed: number;
  today: number;
}

// Tickets Stats
export interface TicketsStats {
  total: number;
  open: number;
  in_progress: number;
  resolved: number;
  closed: number;
}

// Calls List Response
export interface CallsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: VoIPCallFull[];
  stats: CallsStats;
}

// Tickets List Response
export interface TicketsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: TicketFull[];
  stats: TicketsStats;
}

// Taxpayer Types (Είδος Υπόχρεου) - matches Django model choices
export const TAXPAYER_TYPES = [
  { value: 'individual', label: 'Ιδιώτης' },
  { value: 'professional', label: 'Επαγγελματίας' },
  { value: 'company', label: 'Εταιρεία' },
] as const;

// Book Categories (Κατηγορία Βιβλίων)
export const BOOK_CATEGORIES = [
  { value: 'aplografika', label: 'Απλογραφικά' },
  { value: 'diplografika', label: 'Διπλογραφικά' },
  { value: 'no_books', label: 'Χωρίς Βιβλία' },
];

// Legal Forms (Μορφή Επιχείρησης)
export const LEGAL_FORMS = [
  { value: 'AE', label: 'Α.Ε.' },
  { value: 'EPE', label: 'Ε.Π.Ε.' },
  { value: 'IKE', label: 'Ι.Κ.Ε.' },
  { value: 'OE', label: 'Ο.Ε.' },
  { value: 'EE', label: 'Ε.Ε.' },
  { value: 'ATOMIKI', label: 'Ατομική' },
];

// ============================================
// OBLIGATION PROFILE TYPES
// ============================================

// Obligation Type with group info
export interface ObligationTypeWithGroup {
  id: number;
  name: string;
  code: string;
  frequency: 'monthly' | 'quarterly' | 'annual' | 'follows_vat';
  group_id: number | null;
  group_name: string;
  deadline_type?: string;
  deadline_day?: number | null;
}

// Obligation Group (category) with types
export interface ObligationGroup {
  group_id: number | null;
  group_name: string;
  types: ObligationTypeWithGroup[];
}

// Obligation Profile (reusable bundle)
export interface ObligationProfileBundle {
  id: number;
  name: string;
  description?: string;
  obligation_types: ObligationTypeWithGroup[];
}

// Client Obligation Profile response
export interface ClientObligationProfile {
  client_id: number;
  obligation_type_ids: number[];
  obligation_types: ObligationTypeWithGroup[];
  obligation_profile_ids: number[];
  obligation_profiles: ObligationProfileBundle[];
}

// Generate Month Request
export interface GenerateMonthRequest {
  month: number;
  year: number;
  client_ids?: number[];
}

// Generate Month Result
export interface GenerateMonthResult {
  success: boolean;
  created_count: number;
  skipped_count: number;
  clients_processed: number;
  message: string;
  details: Array<{
    client_id: number;
    client_name: string;
    created: string[];
    skipped: string[];
    note?: string;
  }>;
}

// Greek month labels
export const GREEK_MONTHS = [
  { value: 1, label: 'Ιανουάριος' },
  { value: 2, label: 'Φεβρουάριος' },
  { value: 3, label: 'Μάρτιος' },
  { value: 4, label: 'Απρίλιος' },
  { value: 5, label: 'Μάιος' },
  { value: 6, label: 'Ιούνιος' },
  { value: 7, label: 'Ιούλιος' },
  { value: 8, label: 'Αύγουστος' },
  { value: 9, label: 'Σεπτέμβριος' },
  { value: 10, label: 'Οκτώβριος' },
  { value: 11, label: 'Νοέμβριος' },
  { value: 12, label: 'Δεκέμβριος' },
];

// Frequency labels
export const FREQUENCY_LABELS: Record<string, string> = {
  monthly: 'Μηνιαία',
  quarterly: 'Τριμηνιαία',
  annual: 'Ετήσια',
  follows_vat: 'Ακολουθεί ΦΠΑ',
};

// ============================================
// EMAIL TYPES
// ============================================

export interface EmailTemplate {
  id: number;
  name: string;
  description?: string;
  subject: string;
  body_html: string;
  obligation_type?: number | null;
  obligation_type_name?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailPreview {
  subject: string;
  body: string;
  recipient: string;
  recipient_name: string;
}

export interface SendEmailRequest {
  client_id: number;
  subject: string;
  body: string;
  template_id?: number | null;
  attachment_ids?: number[];
}

export interface SendObligationNoticeRequest {
  obligation_id: number;
  template_type: 'reminder' | 'completion' | 'overdue';
  template_id?: number | null;
  include_attachment?: boolean;
  attachment_ids?: number[];
}

export interface CompleteAndNotifyRequest {
  document_id?: number | null;
  file?: File | null;
  save_to_client_folder?: boolean;
  send_email?: boolean;
  attach_to_email?: boolean;
  email_template_id?: number | null;
  notes?: string;
  time_spent?: number | null;
}

export interface BulkCompleteNotifyRequest {
  obligation_ids: number[];
  send_notifications: boolean;
}

export interface EmailSendResult {
  success: boolean;
  message: string;
  email_log_id?: number;
  error?: string;
}

export interface BulkCompleteNotifyResult {
  success: boolean;
  message: string;
  completed_count: number;
  email_results?: {
    sent: number;
    failed: number;
    skipped: number;
    details: Array<{
      obligation_id: number;
      client: string;
      status: 'sent' | 'failed' | 'skipped';
      message: string;
    }>;
  };
}

// ============================================
// DOCUMENT UPLOAD TYPES
// ============================================

export interface DocumentUploadRequest {
  file: File;
  client_id: number;
  obligation_id?: number | null;
  document_category?: string;
  description?: string;
}

export interface DocumentUploadResult {
  message: string;
  document: ClientDocument;
}

// Document Category labels
export const DOCUMENT_CATEGORY_LABELS: Record<string, string> = {
  contracts: 'Συμβάσεις',
  invoices: 'Τιμολόγια',
  tax: 'Φορολογικά',
  myf: 'ΜΥΦ',
  vat: 'ΦΠΑ',
  payroll: 'Μισθοδοσία',
  general: 'Γενικά',
};

// ============================================
// OBLIGATION SETTINGS TYPES
// ============================================

// Full ObligationType for settings management
export interface ObligationTypeFull {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  frequency: 'monthly' | 'quarterly' | 'annual' | 'follows_vat';
  deadline_type: 'last_day' | 'specific_day' | 'last_day_prev' | 'last_day_next';
  deadline_day: number | null;
  applicable_months?: string | null;
  exclusion_group: number | null;
  exclusion_group_name: string | null;
  profiles: number[];  // ManyToMany - array of profile IDs
  profile_names: string[];  // Array of profile names
  priority: number;
  is_active: boolean;
}

// Form data for creating/updating ObligationType
export interface ObligationTypeFormData {
  code: string;
  name: string;
  description?: string;
  frequency: string;
  deadline_type: string;
  deadline_day?: number | null;
  applicable_months?: string;
  exclusion_group?: number | null;
  profiles?: number[];  // ManyToMany - array of profile IDs
  priority?: number;
  is_active: boolean;
}

// Full ObligationProfile for settings management
export interface ObligationProfileFull {
  id: number;
  name: string;
  description: string | null;
  obligation_types_count: number;
  obligation_types: Array<{ id: number; name: string; code: string }>;
}

// Form data for creating/updating ObligationProfile
export interface ObligationProfileFormData {
  name: string;
  description?: string;
}

// Full ObligationGroup (exclusion group) for settings management
export interface ObligationGroupFull {
  id: number;
  name: string;
  description: string | null;
  obligation_types: number[];
  obligation_type_names: string[];
}

// Form data for creating/updating ObligationGroup
export interface ObligationGroupFormData {
  name: string;
  description?: string;
  obligation_types?: number[];
}

// Deadline type labels
export const DEADLINE_TYPE_LABELS: Record<string, string> = {
  last_day: 'Τέλος μήνα',
  specific_day: 'Συγκεκριμένη ημέρα',
  last_day_prev: 'Τέλος προηγ. μήνα',
  last_day_next: 'Τέλος επόμ. μήνα',
};

// Frequency options for forms
export const FREQUENCY_OPTIONS = [
  { value: 'monthly', label: 'Μηνιαίο' },
  { value: 'quarterly', label: 'Τριμηνιαίο' },
  { value: 'annual', label: 'Ετήσιο' },
  { value: 'follows_vat', label: 'Ακολουθεί ΦΠΑ' },
];

// Deadline type options for forms
export const DEADLINE_TYPE_OPTIONS = [
  { value: 'last_day', label: 'Τέλος μήνα' },
  { value: 'specific_day', label: 'Συγκεκριμένη ημέρα' },
  { value: 'last_day_prev', label: 'Τέλος προηγ. μήνα' },
  { value: 'last_day_next', label: 'Τέλος επόμ. μήνα' },
];
