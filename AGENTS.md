# AI Development Rules

Read CLAUDE.md before making changes.

## Mandatory rules

- Never commit directly to main.
- Always work through a separate branch and pull request.
- Never merge a pull request automatically.
- Never commit passwords, API keys, tokens, credentials, or other secrets.
- Run the relevant project tests before declaring implementation work complete.
- Do not modify production configuration without explicit approval.
- Do not perform destructive database operations without explicit approval.
- Database migrations require explicit review.
- Authentication, authorization, RBAC, and permission changes require explicit review.
- Prefer small and focused changes.
- Report uncertainty instead of guessing.
- Do not weaken or remove existing tests or security checks just to make CI pass.
