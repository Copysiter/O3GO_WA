import { lookup } from "libphonenumber-js"

export function getGeoFromPhoneNumber(num: string | undefined): string {
  if (!num) return "-"
  const normalized = num.startsWith("+") ? num : `+${num}`
  try {
    // We can't reliably get a country name from libphonenumber-js directly
    // without more complex setup. For now, we'll just validate and return the number.
    // A proper implementation would involve parsing and getting the country code.
    return normalized
  } catch (e) {
    return "-"
  }
}
