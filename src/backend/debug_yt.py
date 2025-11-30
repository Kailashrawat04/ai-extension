from importlib import import_module

yt = import_module("youtube_transcript_api")
YTClass = getattr(yt, "YouTubeTranscriptApi")

def inspect_vid(vid):
    print("\n==============================")
    print("VIDEO:", vid)
    print("==============================")
    try:
        if hasattr(YTClass, "list_transcripts"):
            tl = YTClass.list_transcripts(vid)
            print("list_transcripts succeeded, type:", type(tl))
            try:
                for t in tl:
                    print("-> item type:", type(t),
                          "language_code:", getattr(t, "language_code", None),
                          "language:", getattr(t, "language", None))
            except Exception as e:
                print("Iterating TranscriptList failed:", e)
        else:
            print("YTClass has no list_transcripts; trying YTClass.get_transcript fallback")
            try:
                data = YTClass.get_transcript(vid)
                print("get_transcript returned", type(data),
                      "len:", len(data) if hasattr(data, "__len__") else "n/a")
                if isinstance(data, (list, tuple)) and len(data) > 0:
                    print("first item:", data[0])
            except Exception as e2:
                print("get_transcript failed:", e2)
    except Exception as e:
        print("list_transcripts call failed:", e)

# Test videos
inspect_vid("dQw4w9WgXcQ")   # Rick Astley
inspect_vid("yoEezZD26iM")   # Your video
