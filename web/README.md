# CivicPulse Web — Next.js election dashboard

This frontend is **isolated from Streamlit**. It has country/election navigation, a race explorer, horizontally scrolling candidate cards, and an interactive U.S. map. It is intended for a distinct Vercel deployment; merging this code does not change the Streamlit server.

## What is real now
- **2026 U.S.**: Congressional seat registry, real official Iowa and Ohio candidate rosters (with direct source links), source availability and refresh status. Election vote percentages appear **only after published vote counts exist**.
- **2024 U.S.**: Archived House/Senate results from state election offices relayed by Open America. Select "2024 Historical replay" or "Explore 2024 results" to inspect actual published counts and percentages.
- **Nigeria 2027**: Explicitly marked unintegrated. No Nigerian election results fabricated.

The Open America API is free and covers 22 states; it does **not** publish 2026 candidates before vote reports, nor does it serve all states. Candidate roster records are separately sourced. The app never mistakes vote leads, candidate rosters or estimates for certified results.

Source contract: https://openamerica.io/elections/api/

## Local development
From `web/`:

```bash
npm install
npm run dev
npm run build
```

## Deploy as an **independent** Vercel project
1. Import the existing GitHub repository `Dav-lopez/mid-elections`.
2. **Set Project Settings → Build and Deployment → Root Directory to `web`**. This setting is required; root is a Python Streamlit project, not a Next.js app.
3. Confirm Framework Preset `Next.js` and deploy the feature branch to a **preview** first.
4. Check candidate roster, geographic map, historical results, mobile layout, and feed error handling in the preview.
5. Merge through review and promote the Vercel project separately. Never redirect or replace the Streamlit site as part of this rollout.

No API key is needed for Open America. The data feed is fetched directly from visitors' browsers with documented cross-origin support and a source link. Production live-data validation still depends on the provider being reachable when deployed.
