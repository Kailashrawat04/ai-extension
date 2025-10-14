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
});
