# npm audit remediation

## Baseline

The initial audit reported six high-severity findings in the frontend dependency tree. The production-only audit identified four high-severity groups: `nanoid`, `next`, `postcss`, and `sharp`.

## Remediation

| Package | Role | Fix applied | Reason |
|---|---|---|---|
| `nanoid` | Transitive dependency | Ran `npm audit fix` without force | Applied the compatible patched transitive version without a major application upgrade |
| `next` | Direct dependency | Upgraded from `16.2.10` to `16.3.3` | The audit remediation explicitly identified `16.3.3` as the patched compatible release |
| `postcss` | Transitive dependency of Next/Tailwind tooling | Refreshed through the Next.js upgrade and lockfile resolution | Avoided pinning a transitive package manually |
| `sharp` | Next image/runtime dependency | Refreshed through the Next.js upgrade and lockfile resolution | The vulnerable range was below the patched Sharp release selected by the resolved tree |

Do not use `npm audit fix --force` blindly. It can make out-of-range framework changes. If a future audit reintroduces a vulnerability, inspect `npm audit --json`, identify whether it is direct or transitive, upgrade the direct owner first, and then rebuild.

## Verification

```powershell
Set-Location 'D:\Study\Studio Project\3d-ai-stylist\web'
npm audit
npm audit --omit=dev
npm run build
```

Current verification result: `found 0 vulnerabilities`; Next.js build completed successfully with TypeScript checking enabled.
