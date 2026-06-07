import { test, expect } from '@playwright/test'

/**
 * E2E: client portal isolation & navigation.
 *
 * A logged-in client lands on THEIR portal (not the staff app), sees their own
 * ΑΦΜ, can switch tabs, and logging out returns to the login page. Runs against
 * seed_demo data (client 099000117 / Demo2025!).
 */
const USERNAME = '099000117'
const PASSWORD = 'Demo2025!'

test('client lands on own portal, sees own ΑΦΜ, can switch tabs, logs out', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Όνομα χρήστη').fill(USERNAME)
  await page.getByLabel('Κωδικός').fill(PASSWORD)
  await page.getByRole('button', { name: /Σύνδεση/ }).click()

  // Lands on the client portal (not a staff route).
  await expect(page).toHaveURL(/\/portal/, { timeout: 15_000 })

  // Header shows the logged-in client's own ΑΦΜ.
  await expect(page.getByText(new RegExp(`ΑΦΜ:\\s*${USERNAME}`))).toBeVisible()

  // The four portal tabs are present and switchable.
  for (const name of ['Επισκόπηση', 'Υποχρεώσεις', 'ΦΠΑ', 'Έγγραφα']) {
    await page.getByRole('tab', { name }).click()
  }

  // Obligations tab renders its table/empty-state without error.
  await page.getByRole('tab', { name: 'Υποχρεώσεις' }).click()
  await expect(page.getByRole('tab', { name: 'Υποχρεώσεις' })).toHaveAttribute('aria-selected', 'true')

  // Logout returns to login.
  await page.getByRole('button', { name: 'Αποσύνδεση' }).click()
  await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
})

test('a staff-only route does not render the staff app for a client', async ({ page }) => {
  // Log in first.
  await page.goto('/login')
  await page.getByLabel('Όνομα χρήστη').fill(USERNAME)
  await page.getByLabel('Κωδικός').fill(PASSWORD)
  await page.getByRole('button', { name: /Σύνδεση/ }).click()
  await expect(page).toHaveURL(/\/portal/, { timeout: 15_000 })

  // Attempt to visit a staff route directly. The ClientRoute guard must keep the
  // client out of the staff app (redirect away from /dashboard).
  await page.goto('/dashboard')
  await expect(page).not.toHaveURL(/\/dashboard$/, { timeout: 10_000 })
})
