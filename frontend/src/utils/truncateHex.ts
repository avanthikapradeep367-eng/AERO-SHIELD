/** Shortens a 0x-prefixed hash/address to `0x1234…abcd` for display. */
export function truncateHex(value: string, lead = 6, trail = 4): string {
  if (value.length <= lead + trail + 2) {
    return value;
  }
  const prefix = value.startsWith("0x") ? value.slice(0, lead + 2) : value.slice(0, lead);
  const suffix = value.slice(-trail);
  return `${prefix}…${suffix}`;
}
