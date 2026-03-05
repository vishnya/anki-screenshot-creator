require("hs.ipc")

local SERVER   = "http://localhost:5789"
local INCOMING = os.getenv("HOME") .. "/AnkiFox/incoming"
os.execute("mkdir -p " .. INCOMING)

local function getSession()
  local code, body = hs.http.get(SERVER .. "/api/session", {})
  if code == 200 then
    local ok, r = pcall(hs.json.decode, body)
    return ok and r or nil
  end
  return nil
end

local function takeScreenshot()
  local ts   = os.date("%Y%m%d_%H%M%S")
  local path = INCOMING .. "/screenshot_" .. ts .. ".png"
  hs.task.new("/usr/sbin/screencapture", nil, {"-i", path}):start()
end

-- ⌥⇧A: screenshot if session active, else open config page
hs.hotkey.bind({"alt", "shift"}, "a", function()
  local s = getSession()
  if s and s.active then
    takeScreenshot()
  else
    hs.urlevent.openURL(SERVER)
    if not s then
      hs.alert.show("Server not running — check /tmp/anki-fox.log")
    end
  end
end)

-- ⌥⇧⌘A: stop session and reopen config page
hs.hotkey.bind({"alt", "shift", "cmd"}, "a", function()
  hs.http.asyncPost(SERVER .. "/api/session/stop", "", {}, function() end)
  hs.urlevent.openURL(SERVER)
end)

hs.alert.show("anki-fox loaded — ⌥⇧A ready")
