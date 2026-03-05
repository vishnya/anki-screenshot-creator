# Ensure anki-fox server is running and open the config page
anki() {
  local plist="$HOME/Library/LaunchAgents/com.anki-fox.plist"
  if ! curl -sf http://localhost:5789/api/session > /dev/null 2>&1; then
    if [ -f "$plist" ]; then
      echo "Starting anki-fox server..."
      launchctl load "$plist" 2>/dev/null || true
      sleep 2
    else
      echo "Server not installed. Run install.sh first."
      return 1
    fi
  fi
  open http://localhost:5789
}
