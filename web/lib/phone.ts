export function normalizeForGeo(num: string | undefined): string | undefined {
  if (!num) return num
  return num.startsWith("+") ? num : `+${num}`
}

export default normalizeForGeo
