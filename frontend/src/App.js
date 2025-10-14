// src/App.js
import React, { useState } from "react";
import axios from "axios";
import "./App.css";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:5000";

function App() {
  const [text, setText] = useState("");
  const [summary, setSummary] = useState("");
  const [file, setFile] = useState(null);
  const [youtubeURL, setYoutubeURL] = useState("");
  const [mode, setMode] = useState("text");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  const MAX_PDF_BYTES = 10 * 1024 * 1024; // 10 MB

  const resetProgress = () => setProgress(0);

  const handleFileChange = (e) => {
    const f = e.target.files?.[0] ?? null;
    if (f && f.size > MAX_PDF_BYTES) {
      alert("File too large. Please upload a PDF smaller than 10 MB.");
      e.target.value = ""; // clear file input
      setFile(null);
      return;
    }
    setFile(f);
  };

  const isInputValid = () => {
    if (mode === "text") return text.trim().length > 0;
    if (mode === "pdf") return file !== null;
    if (mode === "youtube") return youtubeURL.trim().length > 0;
    return false;
  };

  const handleSummarize = async () => {
    if (!isInputValid()) {
      alert("Please provide valid input for the selected mode.");
      return;
    }

    setLoading(true);
    setSummary("");
    resetProgress();

    try {
      let res;

      if (mode === "text") {
        res = await axios.post(
          `${API_BASE}/summarize/text`,
          { text },
          { timeout: 120000 } // 2 min timeout for long text
        );
      } else if (mode === "pdf") {
        const formData = new FormData();
        formData.append("file", file);
        res = await axios.post(`${API_BASE}/summarize/pdf`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 180000,
          onUploadProgress: (evt) => {
            if (evt.total) {
              const p = Math.round((evt.loaded / evt.total) * 100);
              setProgress(p);
            }
          },
        });
      } else if (mode === "youtube") {
        res = await axios.post(
          `${API_BASE}/summarize/youtube`,
          { video_url: youtubeURL },
          { timeout: 180000 }
        );
      }

      // robustly handle response
      if (res && res.data) {
        if (res.data.summary) {
          setSummary(res.data.summary);
        } else if (res.data.error) {
          // server returned a structured error
          alert("Server error: " + res.data.error);
        } else {
          setSummary(JSON.stringify(res.data));
        }
      } else {
        alert("No response from server");
      }
    } catch (err) {
      console.error(err);
      // try to show a helpful message
      const msg =
        err?.response?.data?.error ||
        err?.message ||
        "Unexpected error. Check server logs.";
      alert("Error: " + msg);
    } finally {
      setLoading(false);
      setProgress(0);
    }
  };

  const clearAll = () => {
    setText("");
    setFile(null);
    setYoutubeURL("");
    setSummary("");
    resetProgress();
  };

  return (
    <div className="app">
      <h1>🧠 AI Summarizer (Text, PDF & YouTube)</h1>

      <div className="mode-buttons">
        <button className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>
          Text
        </button>
        <button className={mode === "pdf" ? "active" : ""} onClick={() => setMode("pdf")}>
          PDF
        </button>
        <button className={mode === "youtube" ? "active" : ""} onClick={() => setMode("youtube")}>
          YouTube
        </button>
      </div>

      <div className="input-area">
        {mode === "text" && (
          <textarea
            placeholder="Paste your text here..."
            rows="10"
            value={text}
            onChange={(e) => setText(e.target.value)}
          ></textarea>
        )}

        {mode === "pdf" && (
          <div className="pdf-input">
            <input type="file" accept="application/pdf" onChange={handleFileChange} />
            {file && (
              <div className="file-info">
                <strong>Selected:</strong> {file.name} ({Math.round(file.size / 1024)} KB)
                <button onClick={() => setFile(null)} className="small-btn">Remove</button>
              </div>
            )}
            <div className="hint">Max file size: 10 MB</div>
            {progress > 0 && <div className="progress">Uploading: {progress}%</div>}
          </div>
        )}

        {mode === "youtube" && (
          <input
            type="text"
            placeholder="Enter YouTube video URL..."
            value={youtubeURL}
            onChange={(e) => setYoutubeURL(e.target.value)}
          />
        )}
      </div>

      <div className="controls">
        <button onClick={handleSummarize} disabled={loading || !isInputValid()}>
          {loading ? "Summarizing..." : "Summarize"}
        </button>
        <button onClick={clearAll} className="secondary">
          Clear
        </button>
      </div>

      {summary && (
        <div className="summary">
          <h2>📝 Summary</h2>
          <pre style={{ whiteSpace: "pre-wrap" }}>{summary}</pre>
          <div className="summary-actions">
            <button
              onClick={() => {
                navigator.clipboard.writeText(summary);
                alert("Summary copied to clipboard");
              }}
            >
              Copy
            </button>
            <a
              href={`data:text/plain;charset=utf-8,${encodeURIComponent(summary)}`}
              download="summary.txt"
            >
              <button>Download</button>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
