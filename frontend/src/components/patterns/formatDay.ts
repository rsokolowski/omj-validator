/** "2026-10-05" -> "5.10.2026" (a calendar day, no time zone shift). */
export function formatDay(isoDay: string): string {
  const [year, month, day] = isoDay.split("-").map(Number);
  if (!year || !month || !day) return isoDay;
  return `${day}.${String(month).padStart(2, "0")}.${year}`;
}
