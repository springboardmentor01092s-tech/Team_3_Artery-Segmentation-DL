# UI wireframes

```text
Login
┌────────────────────────────┐
│ Artery preprocessing       │
│ Email                      │
│ Password                   │
│ [ Sign in ]                │
│ Register link              │
└────────────────────────────┘

App shell
┌──────────┬───────────────────────────────┐
│ Nav      │ Header (user, logout)         │
│ Dashboard│ Disclaimer banner             │
│ Cases    │ Page content                  │
│ Preprocess│                              │
│ Profile  │                              │
└──────────┴───────────────────────────────┘

Preprocessing
┌────────────┬──────────────┬──────────────┐
│ Case       │ Original     │ Preprocessed │
│ Options    │ Image        │ Image        │
│ [Start]    │ WxH, format  │ duration     │
└────────────┴──────────────┴──────────────┘
```

Desktop: original and processed views sit side by side. Smaller screens stack them (`md:grid-cols-2`).
