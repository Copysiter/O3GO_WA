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
}
