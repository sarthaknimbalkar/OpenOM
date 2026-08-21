// The broker's LOCAL calendar date for assertedDate. Using toISOString() would stamp the UTC date -
// for negative-offset zones (all of the US) that is tomorrow's date for the last hours of the day,
// mis-stating a legal assertion date ([#64]). getFullYear/getMonth/getDate read local components.

export function localDateISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
