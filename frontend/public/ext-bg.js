// Open the copilot in Chrome's Side Panel when the toolbar icon is clicked
// (stays beside the Teams/Zoom tab). Falls back to a full tab if unavailable.
const cx = globalThis.chrome;

cx.runtime.onInstalled.addListener(() => {
  try { cx.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }); } catch (e) {}
});

cx.action.onClicked.addListener(async (tab) => {
  try {
    await cx.sidePanel.open({ tabId: tab.id });
  } catch (e) {
    const url = cx.runtime.getURL("index.html");
    const existing = await cx.tabs.query({ url });
    if (existing && existing.length) cx.tabs.update(existing[0].id, { active: true });
    else cx.tabs.create({ url });
  }
});
