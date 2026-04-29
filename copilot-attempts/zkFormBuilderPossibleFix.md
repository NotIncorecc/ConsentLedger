Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/components/ZKConsentFlow.tsx#100-100), lines 100 to 160

The `ZKConsentFlow` component initialises `selectedForm` from `FORM_TEMPLATES[1]` and **never reads the `?form=` URL parameter**. That's the bug — the URL param is generated in `OrgFormBuilder` but never consumed. 

Read [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/components/ZKConsentFlow.tsx#160-160), lines 160 to 400

Found it. `ZKConsentFlow` initialises `selectedForm` from `FORM_TEMPLATES[1]` and **never reads the `?form=` URL param** that `OrgFormBuilder` generates. The fix is to parse the query param on mount and use it. 

Replacing 10 lines with 24 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/components/ZKConsentFlow.tsx)


```

```
Now replace the form template selector section to show the org's form when loaded from URL, instead of the dropdown: 

Replacing 19 lines with 27 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/components/ZKConsentFlow.tsx)


```

```
Now also fix App.tsx — if the URL contains `?form=`, auto-select the user role so the user doesn't have to manually pick it: 

Replacing 2 lines with 4 lines in [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/App.tsx)


```

```


Checked [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/components/ZKConsentFlow.tsx), [](file:///home/gokulganesan/AlgoBharat/consent-ledger/frontend/src/App.tsx), no problems found

Two fixes applied:

1. **ZKConsentFlow.tsx** — now reads `?form=` from the URL on mount. If found, it uses the org's custom form instead of the default KYC template, and shows a blue "Form shared by organisation" banner instead of the dropdown.

2. **App.tsx** — when the URL contains `?form=`, the role is auto-set to `'user'`, so the shared link opens directly into the consent flow without making the user pick a role first.

**Retry the flow:**
- Org clicks "Share Form" → copies URL
- Paste that URL in a new tab → goes straight to user consent flow showing the org's custom form
- Demo mode identity still works fine

Made changes.