"use client"

import { useState, useEffect, useCallback } from "react"
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
} from "@tanstack/react-table"
import { ArrowUpDown, MoreHorizontal, Eye, Edit, Trash2, Search, RefreshCw } from "lucide-react"
import { SimpleFilterButton } from "./table/simple-filter-button"
import { AdvancedSortButton } from "./table/advanced-sort-button"
import { DataTableViewOptions } from "./table/data-table-view-options"
import { DataTablePagination } from "./table/data-table-pagination"
import { useQueryState } from "nuqs"
import { getFiltersStateParser } from "@/lib/parsers"
import type { ExtendedColumnFilter } from "@/types/data-table"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { apiFetch } from "@/lib/api"

// Account type (API response)
export type Account = {
  id: number
  user_id: number
  number: string
  type: number
  session_count: number
  status: number
  created_at: string
  updated_at: string
  info_1: string
  info_2: string
  info_3: string
}

const columnHelper = createColumnHelper<Account>()
const buildOrderBy = (sorting: SortingState) =>
  sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

export const columns = [
  columnHelper.display({
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableHiding: false,
  }),

  columnHelper.accessor("id", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        ID
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => <div className="font-medium">{info.getValue()}</div>,
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "ID", variant: "number", placeholder: "ID" },
  }),

  columnHelper.accessor("number", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}> 
        Number
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Number", variant: "text", placeholder: "Number" },
  }),

  columnHelper.accessor("type", {
    header: "Type",
    cell: (info) => {
      const type = info.getValue()
      return <Badge variant={type === 1 ? "default" : "secondary"}>{type === 1 ? "Premium" : "Standard"}</Badge>
    },
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Type", variant: "select", options: [ { label: "Premium", value: "1" }, { label: "Standard", value: "2" } ] },
  }),

  columnHelper.accessor("status", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}> 
        Status
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => {
      const status = info.getValue()
      return (
        <Badge variant={status === 1 ? "default" : "destructive"}>
          {status === 1 ? "Active" : "Inactive"}
        </Badge>
      )
    },
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Status", variant: "select", options: [ { label: "Active", value: "1" }, { label: "Inactive", value: "0" } ] },
  }),

  columnHelper.accessor("session_count", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}> 
        Sessions
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Sessions", variant: "number", placeholder: ">= 0" },
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}> 
        Created
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Created", variant: "date" },
  }),
  columnHelper.accessor("updated_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}> 
        Updated
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Updated", variant: "date" },
  }),

  columnHelper.display({
    id: "actions",
    cell: () => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="h-8 w-8 p-0">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Actions</DropdownMenuLabel>
          <DropdownMenuItem><Eye className="mr-2 h-4 w-4" /> View</DropdownMenuItem>
          <DropdownMenuItem><Edit className="mr-2 h-4 w-4" /> Edit</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive"><Trash2 className="mr-2 h-4 w-4" /> Delete</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
    enableHiding: false,
  }),
]

export function AccountsTable() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")

  const columnIds = ["id","number","type","status","session_count","created_at","updated_at"]
  const [advFilters] = useQueryState("filters", getFiltersStateParser<Account>(columnIds).withDefault([]))

  const variantMap: Record<string, "text" | "number" | "range" | "date" | "dateRange" | "boolean" | "select" | "multiSelect"> = {
    id: "number",
    number: "text",
    type: "select",
    status: "select",
    session_count: "number",
    created_at: "date",
    updated_at: "date",
  }

  const buildFilterQuery = (filters: ExtendedColumnFilter<Account>[]) => {
    const params: string[] = []
    for (const f of filters) {
      const id = encodeURIComponent(f.id as string)
      const op = f.operator
      const val = f.value
      if (op === "isEmpty" || op === "isNotEmpty") continue
      const add = (suffix: string, value: string) => params.push(`&${id}__${suffix}=${encodeURIComponent(value)}`)
      const variant = variantMap[f.id] ?? "text"
      switch (variant) {
        case "text": {
          const v = String(val)
          if (op === "iLike") add("ilike", `%${v}%`)
          else if (op === "like") add("like", `%${v}%`)
          else if (op === "eq") add("eq", v)
          else if (op === "ne") add("ne", v)
          else add("ilike", `%${v}%`)
          break
        }
        case "number": {
          const v = String(val)
          if (op === "eq" || !op) add("eq", v)
          else if (op === "ne") add("ne", v)
          else if (op === "gt") add("gt", v)
          else if (op === "gte") add("gte", v)
          else if (op === "lt") add("lt", v)
          else if (op === "lte") add("lte", v)
          break
        }
        case "select": {
          add("eq", String(val))
          break
        }
        case "date": {
          const ms = Array.isArray(val) ? val[0] : (val as string)
          if (ms) add("eq", new Date(Number(ms)).toISOString())
          break
        }
        case "dateRange": {
          const arr = Array.isArray(val) ? val : []
          if (arr[0]) add("gte", new Date(Number(arr[0])).toISOString())
          if (arr[1]) add("lte", new Date(Number(arr[1])).toISOString())
          break
        }
        default:
          break
      }
    }
    return params.join("")
  }

  const fetchAccounts = useCallback(
    async (
      pageIndex: number = 0,
      sortingState: SortingState = [],
      columnFiltersState: ColumnFiltersState = [],
      _filter = "",
    ) => {
      try {
        setLoading(true)
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const filtersBasic = columnFiltersState
          .map((f) => (f.value ? `&${encodeURIComponent(f.id)}__ilike=${encodeURIComponent(`%${String(f.value)}%`)}` : ""))
          .join("")
        const filtersAdvanced = buildFilterQuery(advFilters as ExtendedColumnFilter<Account>[])
        const res = await apiFetch(`/accounts/?skip=${pageIndex * 10}&limit=10${orderBy}${filtersBasic}${filtersAdvanced}`)
        const result = res.data ?? res.items ?? res
        setAccounts(Array.isArray(result) ? result : [])
      } catch (err) {
        console.error("Failed to load accounts:", err)
        setAccounts([])
      } finally {
        setLoading(false)
      }
    },
    [advFilters]
  )

  useEffect(() => {
    fetchAccounts(0, sorting, columnFilters, globalFilter)
  }, [fetchAccounts])
  useEffect(() => {
    fetchAccounts(0, sorting, columnFilters, globalFilter)
  }, [sorting, columnFilters, globalFilter, fetchAccounts])

  const table = useReactTable({
    data: accounts,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  })

  if (loading) return <div className="p-4">Loading accounts...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Accounts</CardTitle>
          <Button variant="outline" size="sm" onClick={() => fetchAccounts(table.getState().pagination.pageIndex, sorting, columnFilters, globalFilter)}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
        </div>
        <div className="flex items-center justify-between gap-2 mt-2">
          <div className="flex items-center gap-2">
            <SimpleFilterButton table={table} />
            <AdvancedSortButton table={table} />
            <DataTableViewOptions table={table} />
          </div>
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search accounts..."
              value={globalFilter ?? ""}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="max-w-sm"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id} data-state={row.getIsSelected() && "selected"}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center">No data.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="mt-4">
          <DataTablePagination 
            table={table} 
            onPageChange={(page) => fetchAccounts(page, sorting, columnFilters, globalFilter)}
          />
        </div>
      </CardContent>
    </Card>
  )
}
