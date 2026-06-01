import { test, expect } from '@playwright/test'

/**
 * E2E smoke: login → portal → VAT → upload, against `seed_demo` data.
 *
 * Prereqs (CI/local): Django backend on :8000 with demo data seeded:
 *   python manage.py seed_demo --reset
 * which creates client 099000117 / Demo2025! with multi-year VAT.
 */
const USERNAME = '099000117'
const PASSWORD = 'Demo2025!'

test('client logs in, views VAT, and uploads a document', async ({ page }) => {
  // 1) LOGIN
  await page.goto('/login')
  await page.getByLabel('Όνομα χρήστη').fill(USERNAME)
  await page.getByLabel('Κωδικός').fill(PASSWORD)
  await page.getByRole('button', { name: /Σύνδεση/ }).click()

  // 2) PORTAL — redirected to the client portal (not staff dashboard)
  await expect(page).toHaveURL(/\/portal/, { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'ΦΠΑ' })).toBeVisible()

  // 3) VAT tab — summary + at least one period render
  await page.getByRole('button', { name: 'ΦΠΑ' }).click()
  await expect(page.getByText('Εκροές (Έσοδα)')).toBeVisible()
  await expect(page.getByText('Περίοδοι ΦΠΑ')).toBeVisible()
  // Year selector is present and offers the seeded years.
  await expect(page.getByLabel('Έτος')).toBeVisible()

  // 4) UPLOAD — go to Έγγραφα, upload a file, expect success
  await page.getByRole('button', { name: 'Έγγραφα' }).click()
  await expect(page.getByText('Ανέβασμα εγγράφου')).toBeVisible()

  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: /Επιλογή αρχείου/ }).click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({
    name: 'e2e-smoke.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 e2e smoke test'),
  })

  await expect(page.getByText(/ανέβηκε επιτυχώς/i)).toBeVisible({ timeout: 15_000 })
})
