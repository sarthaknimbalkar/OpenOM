// #127 message-origin gate, extracted as a pure function so its security-critical logic is unit
// tested (its absence let a real bug ship — see below). MV3 without externally_connectable already
// keeps web pages out; this is defense-in-depth for a future connectable/content-script compromise.
//
// The confinement rule: a message from a CONTENT SCRIPT (which runs in the hostile host-page world)
// may ONLY ask for read-only badge state — never trigger a fetch, an embed, or a settings write.
//
// The bug this replaces: `fromContentScript = sender.tab !== undefined` misclassified our OWN
// extension pages. An extension page hosted in a TAB — the popup opened as a `?url=` deep-link / a
// shareable check-link, the author side panel — also has `sender.tab` set, so every non-linkbadge
// message from those contexts was rejected (no response → the popup crashed with
// "'in' operator ... in undefined"). A content script is distinguished not by having a tab, but by
// its sender URL being the host WEB page (http(s)://…) rather than chrome-extension://<id>/….

/** The minimal shape of a MV3 message sender we depend on (chrome.runtime.MessageSender subset). */
export interface MessageSender {
  id?: string;
  url?: string;
  tab?: unknown;
}

/** Messages a content script (hostile-page world) is allowed to send. Read-only, no side effects. */
export const CONTENT_SCRIPT_ALLOWED = [
  "linkbadge:enabled",
  "linkbadge:verify",
] as const;

/**
 * True when the sender is a content script: it has an associated tab AND its URL is a real web page
 * (not one of our own chrome-extension:// pages). A missing/again-non-extension URL with a tab is
 * treated as a content script too (restrictive by default).
 */
export function isContentScript(sender: MessageSender): boolean {
  if (sender.tab === undefined) return false; // extension worker / real toolbar popup — never a CS
  return !sender.url?.startsWith("chrome-extension://");
}

/**
 * Decide whether the service worker should handle a message. Reject if it is not from this
 * extension, or if it is from a content script asking for anything beyond the read-only badge verbs.
 */
export function accepts(
  sender: MessageSender,
  msgType: unknown,
  runtimeId: string,
): boolean {
  if (sender.id !== runtimeId) return false;
  if (isContentScript(sender)) {
    return (CONTENT_SCRIPT_ALLOWED as readonly unknown[]).includes(msgType);
  }
  return true;
}
