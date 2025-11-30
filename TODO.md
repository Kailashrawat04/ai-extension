# TODO: Fix YouTube URL Validation Case Sensitivity Issue

## Information Gathered
- Frontend `isValidYouTubeURL` in `frontend/src/App.js` uses regex patterns that are case-sensitive.
- Backend `extract_video_id` in `Backend/app.py` uses regex patterns that are case-sensitive.
- YouTube URLs can contain uppercase letters (e.g., "YouTube.com"), causing validation mismatches between frontend and backend.
- This leads to 400 errors when the backend rejects URLs that the frontend accepts.

## Plan
- Update frontend `isValidYouTubeURL` to use case-insensitive regex matching.
- Update backend `extract_video_id` to use case-insensitive regex searches.
- Ensure both frontend and backend handle URLs with mixed case correctly.

## Dependent Files to Edit
- `frontend/src/App.js`: Modify `isValidYouTubeURL` function to use case-insensitive patterns. ✅ Completed
- `Backend/app.py`: Modify `extract_video_id` function to use `re.IGNORECASE`. ✅ Completed

## Followup Steps
- Test the application with a YouTube URL containing uppercase letters to verify the fix.
- If issues persist, add logging or further debugging.
