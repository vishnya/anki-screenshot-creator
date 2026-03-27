// background service worker — relays timestamp POSTs from content script to server
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type !== "anki-fox-timestamp") return;
  fetch("http://localhost:5789/api/extension/timestamp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(msg.data),
  }).catch(() => {});
});
