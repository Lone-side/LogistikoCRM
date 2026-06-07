import { test, expect, type Page } from '@playwright/test'

/**
 * E2E: client document upload validation (magic-bytes content check).
 *
 * Validates end-to-end the security fix: an executable renamed to .pdf must be
 * rejected on content, while a genuine PDF is accepted. Runs against seed_demo
 * data (client 099000117 / Demo2025!), same prereqs as portal-smoke.spec.ts.
 */
const USERNAME = '099000117'
const PASSWORD = 'Demo2025!'

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Όνομα χρήστη').fill(USERNAME)
  await page.getByLabel('Κωδικός').fill(PASSWORD)
  await page.getByRole('button', { name: /Σύνδεση/ }).click()
  await expect(page).toHaveURL(/\/portal/, { timeout: 15_000 })
}

async function gotoDocuments(page: Page) {
  await page.getByRole('tab', { name: 'Έγγραφα' }).click()
  await expect(page.getByText('Ανέβασμα εγγράφου')).toBeVisible()
}

async function uploadFile(page: Page, file: { name: string; mimeType: string; buffer: Buffer }) {
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: /Επιλογή αρχείου/ }).click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles(file)
}

test('rejects an executable renamed to .pdf (content/extension mismatch)', async ({ page }) => {
  await login(page)
  await gotoDocuments(page)

  // PE/EXE magic bytes 'MZ...' but a .pdf name → backend magic-bytes check → 400.
  await uploadFile(page, {
    name: 'malware.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('MZ\x90\x00\x03 not really a pdf'),
  })

  await expect(
    page.getByText(/δεν ταιριάζει με τον τύπο|ύποπτο|Σφάλμα/i),
  ).toBeVisible({ timeout: 15_000 })
})

test('accepts a genuine PDF', async ({ page }) => {
  await login(page)
  await gotoDocuments(page)

  await uploadFile(page, {
    name: 'genuine.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.7 genuine e2e document'),
  })

  await expect(page.getByText(/ανέβηκε επιτυχώς/i)).toBeVisible({ timeout: 15_000 })
})
