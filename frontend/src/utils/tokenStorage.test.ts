import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  getRememberMe,
  setAccessToken,
  setTokens,
} from './tokenStorage';

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('αποθηκεύει σε localStorage με rememberMe', () => {
    setTokens('acc', 'ref', true);
    expect(localStorage.getItem('accessToken')).toBe('acc');
    expect(sessionStorage.getItem('accessToken')).toBeNull();
    expect(getRememberMe()).toBe(true);
  });

  it('αποθηκεύει σε sessionStorage χωρίς rememberMe', () => {
    setTokens('acc', 'ref', false);
    expect(sessionStorage.getItem('accessToken')).toBe('acc');
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(getRememberMe()).toBe(false);
  });

  it('ΤΟ ΚΡΙΣΙΜΟ: το token διαβάζεται και όταν ζει στο sessionStorage', () => {
    // Ο interceptor διάβαζε μόνο localStorage -> οι κλήσεις έφευγαν χωρίς
    // Authorization όταν το «να με θυμάσαι» ήταν κλειστό.
    setTokens('session-token', 'session-refresh', false);
    expect(getAccessToken()).toBe('session-token');
    expect(getRefreshToken()).toBe('session-refresh');
  });

  it('διαβάζει κανονικά και από localStorage', () => {
    setTokens('local-token', 'local-refresh', true);
    expect(getAccessToken()).toBe('local-token');
    expect(getRefreshToken()).toBe('local-refresh');
  });

  it('δεν αφήνει stale token στο άλλο storage κατά την εναλλαγή', () => {
    setTokens('first', 'first-ref', true);
    setTokens('second', 'second-ref', false);
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(sessionStorage.getItem('accessToken')).toBe('second');
    expect(getAccessToken()).toBe('second');
  });

  it('το refresh ενημερώνει το storage που ήδη χρησιμοποιείται', () => {
    setTokens('old', 'ref', false);
    setAccessToken('renewed');
    expect(sessionStorage.getItem('accessToken')).toBe('renewed');
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(getAccessToken()).toBe('renewed');
  });

  it('το logout καθαρίζει και τα δύο storages', () => {
    setTokens('a', 'b', true);
    sessionStorage.setItem('accessToken', 'stale');
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(sessionStorage.getItem('accessToken')).toBeNull();
  });
});
