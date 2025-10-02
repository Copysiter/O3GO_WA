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
import { useQueryState } from "nuqs"
import { getFiltersStateParser } from "@/lib/parsers"
import type { ExtendedColumnFilter } from "@/types/data-table"

export type Session = {
  id: number
  account_id: number | null
  ext_id: string | null
  msg_count: number | null
  status: number | null
  created_at: string | null
  updated_at: string | null
  info_1: string | null
  info_2: string | null
  info_3: string | null
}

const columnHelper = createColumnHelper<Session>()

const buildOrderBy = (sorting: SortingState) =>
  sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

const formatDate = (val: string | null) => {
  if (!val) return "-"
  return new Date(val).toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

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

  columnHelper.accessor("account_id", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Account ID
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Account ID", variant: "number", placeholder: "Account ID" },
  }),
  columnHelper.accessor("ext_id", {
    header: "External ID",
    enableColumnFilter: true,
    meta: { label: "External ID", variant: "text", placeholder: "External ID" },
  }),
  columnHelper.accessor("msg_count", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Messages
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Messages", variant: "number", placeholder: ">= 0" },
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
      if (status === null) return <Badge variant="outline">Unknown</Badge>
      return (
        <Badge variant={status === 1 ? "default" : "destructive"}>
          {status === 1 ? "Active" : "Inactive"}
        </Badge>
      )
    },
    enableColumnFilter: true,
    meta: {
      label: "Status",
      variant: "select",
      options: [
        { label: "Active", value: "1" },
        { label: "Inactive", value: "0" },
      ],
    },
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Created At
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => formatDate(info.getValue()),
    enableColumnFilter: true,
    meta: { label: "Created", variant: "date" },
  }),
  columnHelper.accessor("updated_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Updated At
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => formatDate(info.getValue()),
    enableColumnFilter: true,
    meta: { label: "Updated", variant: "date" },
  }),
  columnHelper.accessor("info_1", { header: "Info 1", enableHiding: true }),
  columnHelper.accessor("info_2", { header: "Info 2", enableHiding: true }),
  columnHelper.accessor("info_3", { header: "Info 3", enableHiding: true }),

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

export function SessionsLogsTable() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")

  const columnIds = [
    "id",
    "account_id",
    "ext_id",
    "msg_count",
    "status",
    "created_at",
    "updated_at",
    "info_1",
    "info_2",
    "info_3",
  ]
  const [advFilters] = useQueryState(
    "filters",
    getFiltersStateParser<Session>(columnIds).withDefault([]),
  )

  const buildFilterQuery = (filters: ExtendedColumnFilter<Session>[]) => {
    const params: string[] = []
    for (const f of filters) {
      const id = encodeURIComponent(f.id as string)
      const op = f.operator
      const val = f.value
      if (op === "isEmpty" || op === "isNotEmpty") continue

      const add = (suffix: string, value: string) =>
        params.push(`&${id}__${suffix}=${encodeURIComponent(value)}`)

      const variantMap: Record<string, "text" | "number" | "range" | "date" | "dateRange" | "boolean" | "select" | "multiSelect"> = {
        id: "number",
        account_id: "number",
        ext_id: "text",
        msg_count: "number",
        status: "select",
        created_at: "date",
        updated_at: "date",
        info_1: "text",
        info_2: "text",
        info_3: "text",
      }
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
        case "range": {
          const arr = Array.isArray(val) ? val : []
          if (arr[0]) add("gte", String(arr[0]))
          if (arr[1]) add("lte", String(arr[1]))
          break
        }
        case "select": {
          add("eq", String(val))
          break
        }
        case "multiSelect": {
          const arr = Array.isArray(val) ? val : [String(val)]
          add("in", arr.join(","))
          break
        }
        case "boolean": {
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

  const loadData = useCallback(
    async (
      pageIndex: number = 0,
      sortingState: SortingState = [],
      columnFiltersState: ColumnFiltersState = [],
      filter = "",
    ) => {
      setLoading(true)
      try {
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const filtersBasic = columnFiltersState
          .map((f) => (f.value ? `&${encodeURIComponent(f.id)}__ilike=${encodeURIComponent(`%${String(f.value)}%`)}` : ""))
          .join("")
        const filtersAdvanced = buildFilterQuery(advFilters as ExtendedColumnFilter<Session>[])
        const res = await apiFetch(`/sessions/?skip=${pageIndex * 10}&limit=10${orderBy}${filtersBasic}${filtersAdvanced}`)
        setSessions(res?.data ?? [])
      } catch (err) {
        console.error("Error loading sessions:", err)
        setSessions([])
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    loadData(0, sorting, columnFilters, globalFilter)
  }, [loadData])

  useEffect(() => {
    loadData(0, sorting, columnFilters, globalFilter)
  }, [sorting, columnFilters, globalFilter, loadData])

  const table = useReactTable({
    data: sessions ?? [],
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

  if (loading) return <div className="p-4">Loading sessions...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Sessions</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              loadData(
                table.getState().pagination.pageIndex,
                sorting,
                columnFilters,
                globalFilter,
              )
            }
          >
            <RefreshCw className="w-4 h-4 mr-1" /> Refresh
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
            placeholder="Search..."
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
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
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
            onPageChange={(page) => loadData(page, sorting, columnFilters, globalFilter)}
          />
        </div>
      </CardContent>
    </Card>
  )
}
