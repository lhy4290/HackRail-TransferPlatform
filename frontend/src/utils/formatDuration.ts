export function formatTotalDuration(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}分鐘`;
  if (minutes === 0) return `${hours}小時`;
  return `${hours}小時${minutes}分鐘`;
}

export function formatSegmentMinutes(minutes: number): string {
  return `${String(minutes).padStart(2, "0")}分`;
}
