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
import { DataTable } from "@/components/table/data-table"
import { DataTableToolbar } from "@/components/table/data-table-toolbar"
import { apiFetch } from "@/lib/api"
import { formatMessageStatus } from "@/lib/enums"
import { normalizeForGeo } from "@/lib/phone"

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

const formatDate = (val: string | null) => {
  if (!val) return "-"
  const d = new Date(val)
  return d.toLocaleString("ru-RU", {
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
  }),

  columnHelper.accessor("id", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        ID
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => <div className="font-medium">{info.getValue()}</div>,
  }),

  columnHelper.accessor("dst_addr", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Number
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
  }),
  columnHelper.accessor("geo", {
    header: "Geo",
    cell: (info) => <Badge variant="outline">{info.getValue()}</Badge>,
  }),
  columnHelper.accessor("text", {
    header: "Text",
    cell: (info) => (
      <div className="max-w-[200px] truncate" title={info.getValue()}>
        {info.getValue()}
      </div>
    ),
  }),
  columnHelper.accessor("status", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Status
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const status = info.getValue()
      return (
          <Badge variant={status === "Delivered" ? "default" : status === "Pending" ? "secondary" : "destructive"}>
          {status}
        </Badge>
      )
    },
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Created
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const v = info.getValue() as string | null
      return <div>{v ? new Date(v).toISOString().replace('T', ' ').substring(0, 19) : '-'}</div>
    },
  }),
  columnHelper.accessor("sent_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Sent
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const v = info.getValue() as string | null
      return <div>{v ? new Date(v).toISOString().replace('T', ' ').substring(0, 19) : '-'}</div>
    },
  }),
  columnHelper.accessor("updated_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Updated
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const v = info.getValue() as string | null
      return <div>{v ? new Date(v).toISOString().replace('T', ' ').substring(0, 19) : '-'}</div>
    },
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
  const [pageIndex, setPageIndex] = useState(0)

  const buildOrderBy = (sorting: SortingState) => {
    return sorting
      .map((s) => (s.desc ? `-${s.id}` : `${s.id}`))
      .join("&order_by=")
  }

  const fetchMessages = useCallback(async (pageIndex: number = 0, sortingState: SortingState = []) => {
      try {
        setLoading(true)
        const orderBy = sortingState && sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const res = await apiFetch(`/messages/?skip=${pageIndex * 10}&limit=10${orderBy}`)
        const data = Array.isArray(res) ? res : res.data || res.results || []
    const mapped = data.map((msg: any, idx: number) => ({
          id: msg.id ?? msg.session_id ?? `temp-${idx}`,
          dst_addr: msg.number ?? "-",
          geo: msg.geo ?? "-",
          text: [msg.info_1, msg.info_2, msg.info_3].filter(Boolean).join(" ") || "-",
          // status mapping using centralized mapper
          status: formatMessageStatus(msg.status),
          created_at: msg.created_at ?? null,
          sent_at: msg.sent_at ?? null,
          updated_at: msg.updated_at ?? null,
    }))
    // For geo detection we may want to normalize when needed; do not mutate original
    const normalized = mapped.map((m: Message) => ({ ...m, geo: normalizeForGeo(m.dst_addr) || m.geo }))
        setMessages(normalized)
      } catch (err) {
        console.error("Failed to load messages:", err)
      } finally {
        setLoading(false)
      }
    }, [])

  useEffect(() => {
    fetchMessages(pageIndex, sorting)
  }, [fetchMessages, pageIndex, sorting])

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
    onStateChange: (updater) => {
      try {
        const s = typeof updater === 'function' ? updater({} as any) : updater
        const page = (s as any).pagination?.pageIndex ?? 0
        setPageIndex(page)
      } catch (e) {}
    },
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
        <DataTable table={table}>
          <DataTableToolbar table={table}>
            <Button variant="outline" size="sm" onClick={() => fetchMessages(table.getState().pagination.pageIndex, table.getState().sorting)}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}
