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

export type Message = {
  id: number | string
  dst_addr: string
  geo: string
  text: string
  status: string
  created_at: string | null
  sent_at: string | null
  updated_at: string | null
}

const columnHelper = createColumnHelper<Message>()

const buildOrderBy = (sorting: SortingState) =>
  sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

const formatDate = (val: string | null) => {
  if (!val) return "-"
  const d = new Date(val)
  return d.toLocaleString("en-US", {
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

  columnHelper.accessor("dst_addr", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Recipient
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Recipient", variant: "text", placeholder: "Phone/Address" },
  }),
  columnHelper.accessor("geo", {
    header: "Geo",
    cell: (info) => <Badge variant="outline">{info.getValue()}</Badge>,
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Geo", variant: "text", placeholder: "Geo" },
  }),
  columnHelper.accessor("text", {
    header: "Message",
    cell: (info) => (
      <div className="max-w-[200px] truncate" title={info.getValue()}>
        {info.getValue()}
      </div>
    ),
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Message", variant: "text", placeholder: "Search text" },
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
        <Badge
          variant={status === "Delivered" ? "default" : status === "Pending" ? "secondary" : "destructive"}
        >
          {status}
        </Badge>
      )
    },
    enableColumnFilter: true,
    enableHiding: true,
    meta: {
      label: "Status",
      variant: "select",
      options: [
        { label: "Delivered", value: "Delivered" },
        { label: "Pending", value: "Pending" },
        { label: "Failed", value: "Failed" },
      ],
    },
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Created
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => formatDate(info.getValue()),
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Created", variant: "date" },
  }),
  columnHelper.accessor("sent_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Sent
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => formatDate(info.getValue()),
    enableColumnFilter: true,
    enableHiding: true,
    meta: { label: "Sent", variant: "date" },
  }),
  columnHelper.accessor("updated_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Updated
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    enableSorting: true,
    cell: (info) => formatDate(info.getValue()),
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
          <DropdownMenuItem>
            <Eye className="mr-2 h-4 w-4" /> View
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Edit className="mr-2 h-4 w-4" /> Edit
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive">
            <Trash2 className="mr-2 h-4 w-4" /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
    enableHiding: false,
  }),
]

export function MessagesTable() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")

  const columnIds = [
    "id",
    "dst_addr",
    "geo",
    "text",
    "status",
    "created_at",
    "sent_at",
    "updated_at",
  ]
  const filterVariants: Record<string, "text" | "number" | "range" | "date" | "dateRange" | "boolean" | "select" | "multiSelect"> = {
    id: "number",
    dst_addr: "text",
    geo: "text",
    text: "text",
    status: "select",
    created_at: "date",
    sent_at: "date",
    updated_at: "date",
  }
  const [advFilters] = useQueryState(
    "filters",
    getFiltersStateParser<Message>(columnIds).withDefault([]),
  )

  const buildFilterQuery = (filters: ExtendedColumnFilter<Message>[]) => {
    const params: string[] = []
    for (const f of filters) {
      const id = encodeURIComponent(f.id as string)
      const op = f.operator
      const val = f.value
      if (op === "isEmpty" || op === "isNotEmpty") continue

      const add = (suffix: string, value: string) =>
        params.push(`&${id}__${suffix}=${encodeURIComponent(value)}`)

      const variant = filterVariants[f.id] ?? "text"
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

  const fetchMessages = useCallback(
    async (
      pageIndex: number = 0,
      sortingState: SortingState = [],
      columnFiltersState: ColumnFiltersState = [],
      filter = "",
    ) => {
    try {
      setLoading(true)
      const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
      const filtersBasic = columnFiltersState
        .map((f) => (f.value ? `&${encodeURIComponent(f.id)}__ilike=${encodeURIComponent(`%${String(f.value)}%`)}` : ""))
        .join("")
      const filtersAdvanced = buildFilterQuery(advFilters as ExtendedColumnFilter<Message>[])
      const res = await fetch(
        `http://localhost:8000/api/v1/messages/?skip=${pageIndex * 10}&limit=10${orderBy}${filtersBasic}${filtersAdvanced}`,
      )
      const json = await res.json()
      const data = Array.isArray(json) ? json : json.data || []
      const mapped = data.map((msg: any, idx: number) => ({
        id: msg.id ?? msg.session_id ?? `temp-${idx}`,
        dst_addr: msg.number ?? "-",
        geo: msg.geo ?? "-",
        text: [msg.info_1, msg.info_2, msg.info_3].filter(Boolean).join(" ") || "-",
        status: msg.status === 0 ? "Pending" : msg.status === 1 ? "Delivered" : "Failed",
        created_at: msg.created_at ?? null,
        sent_at: msg.sent_at ?? null,
        updated_at: msg.updated_at ?? null,
      }))
      setMessages(mapped)
    } catch (err) {
      console.error("Failed to load messages:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMessages(0, sorting, columnFilters, globalFilter)
  }, [fetchMessages])

  useEffect(() => {
    // refetch on sorting/filters/global
    fetchMessages(0, sorting, columnFilters, globalFilter)
  }, [sorting, columnFilters, globalFilter, fetchMessages])

  const table = useReactTable({
    data: messages,
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

  if (loading) return <div className="p-4">Loading messages...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Messages</CardTitle>

          {/* Refresh button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              fetchMessages(
                table.getState().pagination.pageIndex,
                sorting,
                columnFilters,
                globalFilter,
              )
            }
          >
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
              placeholder="Search messages..."
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
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel()?.rows?.length ? (
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
                  <TableCell colSpan={columns.length} className="h-24 text-center">
                    No messages.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="mt-4">
          <DataTablePagination 
            table={table} 
            onPageChange={(page) => fetchMessages(page, sorting, columnFilters, globalFilter)}
          />
        </div>
      </CardContent>
    </Card>
  )
}
