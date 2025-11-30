import importlib, pprint
yt = importlib.import_module("youtube_transcript_api")
print("\n--- Available attributes in youtube_transcript_api ---")
pprint.pprint([a for a in dir(yt) if not a.startswith("_")])
print("\n--- YouTubeTranscriptApi class ---")
print(getattr(yt, "YouTubeTranscriptApi", None))
print("\n--- Module-level get_transcript callable? ---")
print(callable(getattr(yt, "get_transcript", None)))
