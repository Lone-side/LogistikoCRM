import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '../utils/tokenStorage';

/**
 * Ο rejected handler του response interceptor. Το axios τον κρατά στο
 * `interceptors.response.handlers`· τον καλούμε απευθείας ώστε να δοκιμαστεί η
 * λογική ανανέωσης χωρίς πραγματικό δίκτυο.
 */
type RejectedHandler = (error: unknown) => Promise<unknown>;
const rejectedHandler = (
  apiClient.interceptors.response as unknown as {
    handlers: { rejected: RejectedHandler }[];
  }
).handlers[0].rejected;

function unauthorized(url = '/api/clients/') {
  const config = { url, headers: {} } as InternalAxiosRequestConfig;
  return { response: { status: 401 }, config };
}

describe('apiClient token refresh', () => {
  let postSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    clearTokens();
    // Το retry του αρχικού request δεν πρέπει να βγει στο δίκτυο.
    apiClient.defaults.adapter = vi.fn(async (config) => ({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    })) as never;
    postSpy = vi.spyOn(axios, 'post');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    clearTokens();
  });

  it('αποθηκεύει το ΝΕΟ refresh token μετά από rotation', async () => {
    // Regression: το backend τρέχει με ROTATE_REFRESH_TOKENS +
    // BLACKLIST_AFTER_ROTATION. Αν κρατηθεί μόνο το access, το επόμενο refresh
    // στέλνει blacklisted token και ο χρήστης πετάγεται έξω.
    setTokens('old-access', 'old-refresh', true);
    postSpy.mockResolvedValue({
      data: { access: 'new-access', refresh: 'new-refresh' },
    } as never);

    await rejectedHandler(unauthorized());

    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
  });

  it('στέλνει ΕΝΑ refresh όταν πολλά αιτήματα πάρουν 401 μαζί', async () => {
    // Ένα dashboard στέλνει πολλά queries παράλληλα. Χωρίς ουρά, το πρώτο
    // refresh θα ακύρωνε το token και τα υπόλοιπα θα αποτύγχαναν.
    setTokens('old-access', 'old-refresh', true);
    postSpy.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () => resolve({ data: { access: 'new-access', refresh: 'new-refresh' } }),
            10
          )
        ) as never
    );

    await Promise.all([
      rejectedHandler(unauthorized('/api/clients/')),
      rejectedHandler(unauthorized('/api/obligations/')),
      rejectedHandler(unauthorized('/api/tickets/')),
    ]);

    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(getRefreshToken()).toBe('new-refresh');
  });

  it('δεν κάνει redirect σε 401 χωρίς refresh token', async () => {
    // Τυπικά: λάθος κωδικός στο login. Το σφάλμα πρέπει να φτάσει στον caller
    // για να εμφανιστεί μήνυμα — όχι να πεταχτεί ο χρήστης στο /login.
    const error = unauthorized('/api/auth/login/');

    await expect(rejectedHandler(error)).rejects.toBe(error);
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('υποστηρίζει backend χωρίς rotation (μόνο access στην απάντηση)', async () => {
    setTokens('old-access', 'old-refresh', true);
    postSpy.mockResolvedValue({ data: { access: 'new-access' } } as never);

    await rejectedHandler(unauthorized());

    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('old-refresh');
  });

  it('καθαρίζει τα tokens όταν αποτύχει το refresh', async () => {
    setTokens('old-access', 'expired-refresh', true);
    postSpy.mockRejectedValue(new Error('token blacklisted') as never);

    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: '' },
    });

    await expect(rejectedHandler(unauthorized())).rejects.toThrow(
      'token blacklisted'
    );

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(window.location.href).toBe('/login');

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('δεν ξαναπροσπαθεί σε αίτημα που έχει ήδη γίνει retry', async () => {
    setTokens('old-access', 'old-refresh', true);
    const error = unauthorized();
    (error.config as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;

    await expect(rejectedHandler(error)).rejects.toBe(error);
    expect(postSpy).not.toHaveBeenCalled();
  });
});
