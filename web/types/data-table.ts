export type FilterOperator = string
export type FilterVariant =
  | "text"
  | "number"
  | "range"
  | "date"
  | "dateRange"
  | "boolean"
  | "select"
  | "multiSelect"

export interface ExtendedColumnFilter<TData = any> {
  id: string
  operator: FilterOperator
  value: any
  variant?: FilterVariant
}

export interface ExtendedColumnSort<TData = any> {
  id: Extract<keyof TData, string>
  desc: boolean
}

export type User = {
  id: number
  name: string
  login: string
  created_at: string
}
