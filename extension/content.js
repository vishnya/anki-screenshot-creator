// anki-fox YouTube Timestamp Extension
// Sends current playback position to background worker every 2 seconds.

const POLL_MS = 2000;

function postTimestamp() {
  const video = document.querySelector("video");
  if (!video) return;

  const params = new URLSearchParams(window.location.search);
  const videoId = params.get("v") || "";
  if (!videoId) return;

  chrome.runtime.sendMessage({
    type: "anki-fox-timestamp",
    data: {
      videoId: videoId,
      currentTime: video.currentTime,
      duration: video.duration,
    },
  });
}

setInterval(postTimestamp, POLL_MS);
