/**
 * Ενιαία πηγή αλήθειας για την αποθήκευση των JWT.
 *
 * Ο χρήστης επιλέγει «να με θυμάσαι»:
 *   - ναι  -> localStorage   (επιβιώνει το κλείσιμο του browser)
 *   - όχι  -> sessionStorage (σβήνει με το κλείσιμο της καρτέλας)
 *
 * ΠΡΟΒΛΗΜΑ ΠΟΥ ΛΥΝΕΙ: το authStore έγραφε στο sessionStorage όταν το
 * «να με θυμάσαι» ήταν κλειστό (και καθάριζε ρητά το localStorage), ενώ
 * ο axios interceptor διάβαζε ΜΟΝΟ από localStorage. Αποτέλεσμα: η
 * σύνδεση φαινόταν επιτυχής, αλλά κάθε επόμενη κλήση έφευγε χωρίς
 * Authorization header — δηλαδή το «χωρίς να με θυμάσαι» ήταν σπασμένο.
 *
 * Εδώ η ανάγνωση κοιτά ΚΑΙ ΤΑ ΔΥΟ storages και η εγγραφή/διαγραφή
 * κρατά μία μόνο έγκυρη θέση, ώστε να μη μένουν stale tokens.
 */

export const ACCESS_TOKEN_KEY = 'accessToken';
export const REFRESH_TOKEN_KEY = 'refreshToken';
export const REMEMBER_ME_KEY = 'rememberMe';

const KEYS = [ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, REMEMBER_ME_KEY];

/** Τα διαθέσιμα storages, με ασφάλεια σε SSR/private mode. */
function storages(): Storage[] {
  const list: Storage[] = [];
  try {
    if (typeof localStorage !== 'undefined') list.push(localStorage);
  } catch {
    /* απροσπέλαστο (private mode / disabled) */
  }
  try {
    if (typeof sessionStorage !== 'undefined') list.push(sessionStorage);
  } catch {
    /* απροσπέλαστο */
  }
  return list;
}

/** Διαβάζει από localStorage και, αν λείπει, από sessionStorage. */
function read(key: string): string | null {
  for (const store of storages()) {
    try {
      const value = store.getItem(key);
      if (value) return value;
    } catch {
      /* αγνόησε μη προσβάσιμο storage */
    }
  }
  return null;
}

export function getAccessToken(): string | null {
  return read(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return read(REFRESH_TOKEN_KEY);
}

export function getRememberMe(): boolean {
  return read(REMEMBER_ME_KEY) === 'true';
}

/**
 * Αποθηκεύει τα tokens στο storage που αντιστοιχεί στην επιλογή του
 * χρήστη και καθαρίζει το άλλο, ώστε να μην απομένει stale αντίγραφο.
 */
export function setTokens(
  access: string,
  refresh: string,
  rememberMe: boolean,
): void {
  clearTokens();
  try {
    const target = rememberMe ? localStorage : sessionStorage;
    target.setItem(ACCESS_TOKEN_KEY, access);
    target.setItem(REFRESH_TOKEN_KEY, refresh);
    target.setItem(REMEMBER_ME_KEY, String(rememberMe));
  } catch {
    /* storage μη διαθέσιμο — τα tokens μένουν μόνο στη μνήμη */
  }
}

/** Ενημερώνει μόνο το access token, στο storage που ήδη χρησιμοποιείται. */
export function setAccessToken(access: string): void {
  for (const store of storages()) {
    try {
      if (store.getItem(REFRESH_TOKEN_KEY)) {
        store.setItem(ACCESS_TOKEN_KEY, access);
        return;
      }
    } catch {
      /* αγνόησε */
    }
  }
  // Χωρίς υπάρχον refresh token: σεβασμός της επιλογής «να με θυμάσαι».
  try {
    (getRememberMe() ? localStorage : sessionStorage)
      .setItem(ACCESS_TOKEN_KEY, access);
  } catch {
    /* storage μη διαθέσιμο */
  }
}

/** Καθαρίζει τα tokens από ΟΛΑ τα storages. */
export function clearTokens(): void {
  for (const store of storages()) {
    for (const key of KEYS) {
      try {
        store.removeItem(key);
      } catch {
        /* αγνόησε */
      }
    }
  }
}
