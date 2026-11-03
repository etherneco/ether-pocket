// X11 direct-touch events must reach Firefox's pan/zoom handler.
pref("dom.w3c_touch_events.enabled", 1);
// Distribution defaults; remain user-overridable. No Firefox binary or UI patch.
pref("browser.uidensity", 2);
// Use Firefox's supported server-titlebar mode. EtherSurface removes the
// redundant server decoration while retaining native tabs and the address bar.
pref("browser.tabs.inTitlebar", 0);
