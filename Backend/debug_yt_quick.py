import importlib, inspect, pprint, traceback

VIDEO_ID = "dQw4w9WgXcQ"  # replace with any video id you want to test (Rickroll is reliable)

print("\n== Importing module ==")
yt = importlib.import_module("youtube_transcript_api")
print("module attrs (top-level):")
pprint.pprint([a for a in dir(yt) if not a.startswith("_")])

YTClass = getattr(yt, "YouTubeTranscriptApi", None)
print("\n== YouTubeTranscriptApi class ==")
print(YTClass)
if YTClass:
    print("\nclass attrs (filter*):")
    class_attrs = [a for a in dir(YTClass) if not a.startswith("_")]
    pprint.pprint(class_attrs[:200])

# Build candidate names from actual class attrs and common names
candidates = set()
if YTClass:
    for a in class_attrs:
        low = a.lower()
        if "transcript" in low or "fetch" in low or "list" in low or "get" in low:
            candidates.add(a)

# also try module-level and _api
for a in dir(yt):
    if a.startswith("_"): continue
    low = a.lower()
    if "transcript" in low or "fetch" in low or "list" in low or "get" in low:
        candidates.add(a)

print("\n== Candidate methods to try ==")
pprint.pprint(sorted(candidates))

def attempt_call(fn, desc):
    print(f"\n-- TRY {desc}")
    try:
        res = fn(VIDEO_ID)
        print("SUCCESS (called with single video_id). Type:", type(res))
        if isinstance(res, (list, tuple)):
            print("len:", len(res))
            if len(res) > 0:
                print("first item repr:")
                pprint.pprint(res[0])
        else:
            pprint.pprint(res)
    except TypeError:
        # try passing as list
        try:
            res = fn([VIDEO_ID])
            print("SUCCESS (called with [video_id]). Type:", type(res))
            if isinstance(res, (list, tuple)):
                print("len:", len(res))
                if len(res) > 0:
                    pprint.pprint(res[0])
            else:
                pprint.pprint(res)
        except Exception as e:
            print("FAILED when calling with [video_id]:", type(e).__name__, str(e))
            traceback.print_exc(limit=5)
    except Exception as e:
        print("FAILED:", type(e).__name__, str(e))
        traceback.print_exc(limit=5)

# Try class methods (callable attributes)
if YTClass:
    for name in sorted(candidates):
        if hasattr(YTClass, name):
            fn = getattr(YTClass, name)
            if callable(fn):
                attempt_call(fn, f"YTClass.{name}")

# Try instantiation + instance methods
if YTClass:
    try:
        inst = None
        try:
            inst = YTClass()
            print("\nCreated instance of YouTubeTranscriptApi:", type(inst))
        except Exception as e:
            print("\nCould not instantiate YouTubeTranscriptApi:", type(e).__name__, e)
        if inst:
            for name in sorted(candidates):
                if hasattr(inst, name):
                    fn = getattr(inst, name)
                    if callable(fn):
                        attempt_call(fn, f"inst.{name}")
    except Exception:
        pass

# Try module-level functions
for name in sorted(candidates):
    if hasattr(yt, name):
        fn = getattr(yt, name)
        if callable(fn):
            attempt_call(fn, f"module.{name}")

# Try _api submodule
try:
    api = importlib.import_module("youtube_transcript_api._api")
    print("\n_api attrs sample:", [a for a in dir(api) if not a.startswith("_")][:200])
    for name in sorted(candidates):
        if hasattr(api, name):
            fn = getattr(api, name)
            if callable(fn):
                attempt_call(fn, f"_api.{name}")
except Exception as e:
    print("\n_no _api module or failed to import:", type(e).__name__, str(e))

print("\n== Done debug script ==")
