export const dataTableConfig = {
  sortOrders: [
    { label: "Ascending", value: "asc" as const },
    { label: "Descending", value: "desc" as const },
  ],
  filterVariants: [
    "text",
    "number",
    "range",
    "date",
    "dateRange",
    "boolean",
    "select",
    "multiSelect",
  ] as const,
  operators: [
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "like",
    "iLike",
    "in",
    "notIn",
    "isEmpty",
    "isNotEmpty",
    "isBetween",
    "eqTrue",
    "eqFalse",
  ] as const,
  textOperators: [
    { label: "Contains (case-insensitive)", value: "iLike" },
    { label: "Equals", value: "eq" },
  ],
  numericOperators: [
    { label: "=", value: "eq" },
    { label: ">", value: "gt" },
    { label: "<", value: "lt" },
  ],
  dateOperators: [
    { label: "On", value: "eq" },
    { label: "Before", value: "lt" },
    { label: "After", value: "gt" },
  ],
  booleanOperators: [
    { label: "Is true", value: "eqTrue" },
    { label: "Is false", value: "eqFalse" },
  ],
  selectOperators: [
    { label: "Equals", value: "eq" },
  ],
  multiSelectOperators: [
    { label: "In", value: "in" },
  ],
}
