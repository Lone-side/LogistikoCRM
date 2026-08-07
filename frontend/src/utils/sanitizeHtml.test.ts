import { describe, expect, it } from 'vitest';
import { safeHtml, sanitizeHtml } from './sanitizeHtml';

describe('sanitizeHtml — εξουδετέρωση XSS', () => {
  it('αφαιρεί <script>', () => {
    const out = sanitizeHtml('<p>γεια</p><script>alert(1)</script>');
    expect(out).not.toContain('<script');
    expect(out).not.toContain('alert(1)');
    expect(out).toContain('γεια');
  });

  it('αφαιρεί event handlers (onerror/onload/onclick)', () => {
    for (const dirty of [
      '<img src=x onerror="alert(1)">',
      '<div onload="alert(1)">κείμενο</div>',
      '<p onclick="steal()">κλικ</p>',
      '<img src=x OnErRoR=alert(1)>',
    ]) {
      const out = sanitizeHtml(dirty);
      expect(out.toLowerCase()).not.toContain('onerror');
      expect(out.toLowerCase()).not.toContain('onload');
      expect(out.toLowerCase()).not.toContain('onclick');
      expect(out).not.toContain('alert(1)');
    }
  });

  it('αφαιρεί javascript: URIs', () => {
    const out = sanitizeHtml('<a href="javascript:alert(1)">κλικ</a>');
    expect(out.toLowerCase()).not.toContain('javascript:');
  });

  it('αφαιρεί iframe/object/embed/form', () => {
    for (const tag of ['iframe', 'object', 'embed', 'form']) {
      const out = sanitizeHtml(`<${tag} src="http://evil"></${tag}>`);
      expect(out).not.toContain(`<${tag}`);
    }
  });

  it('αφαιρεί <svg> (mXSS vector)', () => {
    const out = sanitizeHtml('<svg><script>alert(1)</script></svg>');
    expect(out).not.toContain('<svg');
    expect(out).not.toContain('alert(1)');
  });

  it('αφαιρεί data: URI που δεν είναι εικόνα', () => {
    const out = sanitizeHtml(
      '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    );
    expect(out).not.toContain('data:text/html');
  });

  it('αφαιρεί <style> (CSS-based exfiltration)', () => {
    const out = sanitizeHtml('<style>body{background:url(http://evil)}</style><p>ok</p>');
    expect(out).not.toContain('<style');
    expect(out).toContain('ok');
  });
});

describe('sanitizeHtml — διατήρηση νόμιμου περιεχομένου email', () => {
  it('κρατά βασική μορφοποίηση', () => {
    const out = sanitizeHtml(
      '<p><strong>Έντονα</strong> και <em>πλάγια</em><br>νέα γραμμή</p>',
    );
    expect(out).toContain('<strong>');
    expect(out).toContain('<em>');
    expect(out).toContain('Έντονα');
  });

  it('κρατά πίνακες και λίστες', () => {
    const out = sanitizeHtml(
      '<table><tr><td>κελί</td></tr></table><ul><li>στοιχείο</li></ul>',
    );
    expect(out).toContain('<td>');
    expect(out).toContain('<li>');
  });

  it('κρατά ασφαλείς συνδέσμους και εικόνες', () => {
    const out = sanitizeHtml(
      '<a href="https://example.gr">σύνδεσμος</a>' +
      '<img src="https://example.gr/a.png" alt="εικόνα">',
    );
    expect(out).toContain('https://example.gr');
    expect(out).toContain('<img');
    expect(out).toContain('alt="εικόνα"');
  });

  it('κρατά mailto/tel και inline εικόνες email (cid:, data:image)', () => {
    expect(sanitizeHtml('<a href="mailto:a@b.gr">mail</a>')).toContain('mailto:');
    expect(sanitizeHtml('<a href="tel:+302101234567">τηλ</a>')).toContain('tel:');
    expect(sanitizeHtml('<img src="cid:part1">')).toContain('cid:');
    const dataImg = '<img src="data:image/png;base64,iVBORw0KGgo=">';
    expect(sanitizeHtml(dataImg)).toContain('data:image/png');
  });

  it('προσθέτει rel="noopener noreferrer" σε target="_blank"', () => {
    const out = sanitizeHtml('<a href="https://example.gr" target="_blank">x</a>');
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it('κρατά ελληνικούς χαρακτήρες αυτούσιους', () => {
    const out = sanitizeHtml('<p>ΑΦΜ 123456789 — Δήλωση ΦΠΑ Ιανουαρίου</p>');
    expect(out).toContain('ΑΦΜ 123456789');
    expect(out).toContain('Δήλωση ΦΠΑ Ιανουαρίου');
  });
});

describe('sanitizeHtml — οριακές τιμές', () => {
  it('χειρίζεται null/undefined/κενό', () => {
    expect(sanitizeHtml(null)).toBe('');
    expect(sanitizeHtml(undefined)).toBe('');
    expect(sanitizeHtml('')).toBe('');
  });

  it('χειρίζεται μη-string', () => {
    expect(sanitizeHtml(42 as unknown as string)).toBe('');
  });
});

describe('safeHtml helper', () => {
  it('επιστρέφει props έτοιμα για dangerouslySetInnerHTML', () => {
    const props = safeHtml('<p>ok</p><script>alert(1)</script>');
    expect(props.dangerouslySetInnerHTML.__html).toContain('ok');
    expect(props.dangerouslySetInnerHTML.__html).not.toContain('<script');
  });
});
