const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
  ["second", 1],
];

const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

/** Formats an ISO timestamp as a human-relative string, e.g. "5 minutes ago". */
export function relativeTime(isoTimestamp: string): string {
  const then = new Date(isoTimestamp).getTime();
  if (Number.isNaN(then)) {
    return isoTimestamp;
  }

  const diffSeconds = (then - Date.now()) / 1000;
  const absSeconds = Math.abs(diffSeconds);

  for (const [unit, secondsInUnit] of UNITS) {
    if (absSeconds >= secondsInUnit || unit === "second") {
      const value = Math.round(diffSeconds / secondsInUnit);
      return formatter.format(value, unit);
    }
  }

  return formatter.format(0, "second");
}
