import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Το jsx-a11y μόλις μπήκε και βρίσκει 216 προϋπάρχοντα ευρήματα
      // (182 από αυτά label-has-associated-control). Μπαίνουν ως warnings
      // ώστε το χρέος να είναι ΜΕΤΡΗΣΙΜΟ σε κάθε `npm run lint`, χωρίς να
      // σπάσει το μπλοκαριστικό CI gate. Καθώς οι κατηγορίες καθαρίζονται,
      // ανεβάζουμε μία-μία σε 'error' ώστε να μην ξαναγυρίσουν.
      'jsx-a11y/label-has-associated-control': 'warn',
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
      'jsx-a11y/no-noninteractive-element-interactions': 'warn',
      // Το autoFocus είναι σωστό μέσα σε modal (η εστίαση ΠΡΕΠΕΙ να μπει
      // στον διάλογο)· ο κανόνας δεν ξεχωρίζει το context.
      'jsx-a11y/no-autofocus': 'off',
    },
  },
])
