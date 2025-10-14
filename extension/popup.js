// Function to extract video ID from URL
function extractVideoId(url) {
  if (!url) return null;
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  if (url.includes("v=")) {
    try {
      return url.split("v=")[1].split("&")[0];
    } catch (e) {
      return null;
    }
  }
  return null;
}

// Function to fetch and display video title
async function fetchVideoTitle(videoUrl) {
  const videoTitleEl = document.getElementById("videoTitle");
  const videoId = extractVideoId(videoUrl);
  if (!videoId) {
    videoTitleEl.textContent = "";
    return false;
  }

  try {
    const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
    const response = await fetch(oembedUrl);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    videoTitleEl.textContent = `🎥 ${data.title}`;
    return true;
  } catch (err) {
    console.error("Error fetching title:", err);
    videoTitleEl.textContent = "";
    return false;
  }
}

// Function to perform summarization
async function performSummarization(videoUrl) {
  const statusEl = document.getElementById("status");
  const summaryOutput = document.getElementById("summaryOutput");
  summaryOutput.textContent = "";
  statusEl.textContent = "Summarizing... (please wait)";
  try {
    const res = await fetch("http://127.0.0.1:5000/summarize/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url: videoUrl }),
    });

    const data = await res.json();
    if (data.summary) {
      summaryOutput.textContent = data.summary;
      statusEl.textContent = "✅ Summary generated!";
    } else if (data.error) {
      statusEl.textContent = `⚠️ ${data.error}`;
      summaryOutput.textContent = data.detail || "";
    } else {
      statusEl.textContent = "⚠️ Unknown response.";
    }
  } catch (err) {
    console.error(err);
    statusEl.textContent = "❌ Error: Could not reach backend.";
  }
}

// Auto-fetch title and summarize on popup open if on YouTube video page
document.addEventListener("DOMContentLoaded", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.url.includes("youtube.com/watch")) {
    const videoUrl = tab.url;
    // Fetch and display title
    await fetchVideoTitle(videoUrl);
    // Auto-summarize
    await performSummarization(videoUrl);
  }
});

document.getElementById("summarizeBtn").addEventListener("click", async () => {
  const youtubeURLInput = document.getElementById("youtubeURL");
  const statusEl = document.getElementById("status");
  const summaryOutput = document.getElementById("summaryOutput");
  summaryOutput.textContent = "";
  statusEl.textContent = "Fetching video info...";

  // Get video URL
  let videoUrl = youtubeURLInput.value.trim();

  // If empty, get from current tab
  if (!videoUrl) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url.includes("youtube.com/watch")) {
      videoUrl = tab.url;
    } else {
      statusEl.textContent = "❌ Not a YouTube video page.";
      return;
    }
  }

  // Fetch title if not already fetched
  await fetchVideoTitle(videoUrl);

  await performSummarization(videoUrl);
});


