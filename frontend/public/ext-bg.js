/* global chrome */
// Open the copilot in Chrome's Side Panel when the toolbar icon is clicked
// (stays beside the Teams/Zoom tab). Falls back to a full tab if unavailable.
chrome.runtime.onInstalled.addListener(() => {
  try { chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }); } catch (e) {}
});

chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    const url = chrome.runtime.getURL("index.html");
    const existing = await chrome.tabs.query({ url });
    if (existing && existing.length) chrome.tabs.update(existing[0].id, { active: true });
    else chrome.tabs.create({ url });
  }
});
