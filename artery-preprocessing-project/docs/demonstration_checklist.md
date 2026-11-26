# Prototype demonstration checklist

1. Start backend (`uvicorn` on port 8000).
2. Start frontend (`npm run dev` on port 5173).
3. Register a normal user.
4. Log in and reach the dashboard.
5. Confirm `/admin/users` is blocked for the normal user (UI redirect and API 403).
6. Create a case with a synthetic ID.
7. Upload a supported PNG.
8. Attempt a `.txt` or truncated PNG and confirm rejection.
9. View the original image.
10. Run preprocessing with at least one optional operation enabled.
11. View original and preprocessed images together.
12. Confirm the original file bytes/dimensions are unchanged.
13. Re-open the case and show preprocessing history.
14. Log in as a second user and confirm the first case is forbidden.
15. Run `pytest` from `backend`.
16. Optionally show Swagger at `/docs`.

Out of scope for this demo: segmentation masks, stenosis labels, severity percentages, Grad-CAM, or any diagnosis.
