export const dataTableConfig = {
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
