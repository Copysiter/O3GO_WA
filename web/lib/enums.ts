export function formatAccountStatus(status: number | null | undefined) {
  if (status === null || status === undefined) return { label: "Unknown", variant: "outline" }
  switch (status) {
    case 1:
      return { label: "Active", variant: "default" }
    case 0:
      return { label: "Available", variant: "secondary" }
    case 2:
      return { label: "Paused", variant: "secondary" }
    case -1:
      return { label: "Banned", variant: "destructive" }
    default:
      return { label: `Unknown (${status})`, variant: "outline" }
  }
}

export function formatMessageStatus(code: number | null | undefined) {
  if (code === null || code === undefined) return "Unknown"
  switch (code) {
    case 2:
      return "Delivered"
    case 1:
      return "Sent"
    case 0:
      return "Created"
    case -1:
      return "Waiting"
    case 3:
      return "Undelivered"
    case 4:
      return "Failed"
    default:
      return "Unknown"
  }
}

export function formatAccountType(t: number | null | undefined) {
  if (t === 1) return "Regular"
  if (t === 2) return "Business"
  return "Unknown"
}
