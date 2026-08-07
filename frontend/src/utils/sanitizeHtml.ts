import DOMPurify from 'dompurify';

/**
 * Κεντρικός sanitizer για HTML που αποδίδεται με dangerouslySetInnerHTML.
 *
 * ΓΙΑΤΙ ΥΠΑΡΧΕΙ
 * Σώματα email, previews προτύπων και η υπογραφή email είναι HTML που
 * ΠΡΕΠΕΙ να αποδοθεί (escaping δεν είναι επιλογή). Χωρίς sanitizing, ένας
 * χρήστης του γραφείου —ή ένα εισερχόμενο email— μπορεί να εισάγει
 * <script>/onerror και να εκτελέσει κώδικα στη συνεδρία άλλου χρήστη.
 * Επειδή τα JWT ζουν σε localStorage/sessionStorage (προσβάσιμα από JS),
 * αυτό σημαίνει άμεση κλοπή token, όχι απλώς αλλοίωση εμφάνισης.
 *
 * ΠΟΛΙΤΙΚΗ
 * Allow-list προσανατολισμένη σε περιεχόμενο email: μορφοποίηση, πίνακες,
 * λίστες, σύνδεσμοι, εικόνες. Απαγορεύονται εκτελέσιμα και embedding
 * στοιχεία, όλοι οι event handlers, και κάθε URI scheme πέραν των
 * http/https/mailto/tel/cid και data: για εικόνες.
 */

const ALLOWED_TAGS = [
  'a', 'b', 'blockquote', 'br', 'caption', 'code', 'col', 'colgroup',
  'div', 'em', 'figcaption', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'q', 's', 'small', 'span',
  'strike', 'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
  'thead', 'tr', 'u', 'ul',
];

const ALLOWED_ATTR = [
  'align', 'alt', 'border', 'cellpadding', 'cellspacing', 'class', 'colspan',
  'dir', 'height', 'href', 'lang', 'rel', 'rowspan', 'src', 'style', 'target',
  'title', 'valign', 'width',
];

/** http(s), mailto, tel, cid (inline email parts) και data: μόνο για εικόνες. */
const ALLOWED_URI_REGEXP =
  /^(?:(?:https?|mailto|tel|cid):|data:image\/(?:png|jpe?g|gif|webp|bmp);base64,|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i;

let hookRegistered = false;

function registerHooks(): void {
  if (hookRegistered) return;
  // Σύνδεσμοι σε νέα καρτέλα: πάντα rel="noopener noreferrer" ώστε η
  // σελίδα προορισμού να μην αποκτά αναφορά στο window opener.
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node instanceof Element && node.tagName === 'A') {
      if (node.getAttribute('target')) {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
      }
    }
  });
  hookRegistered = true;
}

/**
 * Καθαρίζει HTML ώστε να αποδοθεί με ασφάλεια.
 * Επιστρέφει πάντα string (κενό για null/undefined/μη-string).
 */
export function sanitizeHtml(dirty: string | null | undefined): string {
  if (!dirty || typeof dirty !== 'string') return '';
  registerHooks();
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP,
    // Καμία μορφή <script>, <style>, <iframe>, <object>, <embed>, <form>
    FORBID_TAGS: [
      'script', 'style', 'iframe', 'object', 'embed', 'form', 'input',
      'button', 'textarea', 'select', 'option', 'link', 'meta', 'base',
      'svg', 'math', 'template', 'noscript',
    ],
    FORBID_ATTR: ['srcset', 'formaction', 'ping', 'autofocus'],
    // ΠΡΟΣΟΧΗ: ΟΧΙ USE_PROFILES εδώ — όταν οριστεί, το DOMPurify αγνοεί
    // τα ALLOWED_TAGS/ALLOWED_ATTR και εφαρμόζει το δικό του προφίλ,
    // δηλαδή η παραπάνω allow-list θα ήταν νεκρός κώδικας.
    ALLOW_UNKNOWN_PROTOCOLS: false,
    KEEP_CONTENT: true,
  });
}

/**
 * Helper για χρήση απευθείας σε dangerouslySetInnerHTML:
 *
 *     <div {...safeHtml(email.body)} />
 */
export function safeHtml(dirty: string | null | undefined): {
  dangerouslySetInnerHTML: { __html: string };
} {
  return { dangerouslySetInnerHTML: { __html: sanitizeHtml(dirty) } };
}
