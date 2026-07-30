import { describe, expect, it } from 'vitest';
import { formatAfm, validateAfm, validateAfmChecksum } from './afm';

describe('validateAfm', () => {
  it('δέχεται 9ψήφιο αριθμητικό ΑΦΜ', () => {
    expect(validateAfm('123456783')).toBe(true);
  });

  it('απορρίπτει λάθος μήκος ή μη-ψηφία', () => {
    expect(validateAfm('12345678')).toBe(false);
    expect(validateAfm('1234567890')).toBe(false);
    expect(validateAfm('12345678a')).toBe(false);
    expect(validateAfm('')).toBe(false);
  });
});

describe('validateAfmChecksum', () => {
  it('έγκυρα ΑΦΜ περνούν το checksum', () => {
    // Γνωστά έγκυρα (ίδια με τα backend tests)
    expect(validateAfmChecksum('123456783')).toBe(true);
    expect(validateAfmChecksum('999863881')).toBe(true);
  });

  it('λάθος check digit αποτυγχάνει', () => {
    expect(validateAfmChecksum('123456782')).toBe(false);
    expect(validateAfmChecksum('123456784')).toBe(false);
  });

  it('μη έγκυρη μορφή αποτυγχάνει', () => {
    expect(validateAfmChecksum('abc')).toBe(false);
  });
});

describe('formatAfm', () => {
  it('χωρίζει σε τριάδες', () => {
    expect(formatAfm('123456789')).toBe('123 456 789');
  });

  it('επιστρέφει ως έχει σε λάθος μήκος', () => {
    expect(formatAfm('12345')).toBe('12345');
  });
});
