# TODO: Add Mood Analysis Feature to YouTube Summarizer

## Tasks
- [x] Extract timestamps from YouTube transcript in /summarize/youtube endpoint
- [x] Implement interval chunking (e.g., 30-second intervals) for transcript text
- [x] Add sentiment analysis function using Hugging Face model (e.g., cardiffnlp/twitter-roberta-base-sentiment)
- [x] Integrate mood analysis into the endpoint, making it optional via query param
- [x] Update JSON response to include mood intervals alongside summary
- [x] Test the updated endpoint with a sample YouTube video
