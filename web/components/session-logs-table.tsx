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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatAccountStatus } from "@/lib/enums"
import { DataTable } from "@/components/table/data-table"
import { DataTableToolbar } from "@/components/table/data-table-toolbar"
import { apiFetch } from "@/lib/api"

export type Session = {
  id: number
  account_id: number | null
  account?: { number?: string }
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

const formatDate = (val: string | null) => {
  if (!val) return "-"
  return new Date(val).toISOString().replace("T", " ").substring(0, 19)
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

  columnHelper.accessor("account", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Account
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const acc = info.getValue() as any
      return <div>{acc?.number ?? "-"}</div>
    },
  }),
  columnHelper.accessor("ext_id", { header: "External ID" }),
  columnHelper.accessor("msg_count", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Messages
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
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
      const status = info.getValue() as number | null
      const mapped = formatAccountStatus(status)
      return <Badge variant={mapped.variant as any}>{mapped.label}</Badge>
    },
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Created
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => formatDate(info.getValue()),
  }),
  columnHelper.accessor("updated_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Updated
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => formatDate(info.getValue()),
  }),
  columnHelper.accessor("info_1", { header: "Info 1" }),
  columnHelper.accessor("info_2", { header: "Info 2" }),
  columnHelper.accessor("info_3", { header: "Info 3" }),

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
  const [pageIndex, setPageIndex] = useState(0)

  const buildOrderBy = (sorting: SortingState) => {
    return sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join("&order_by=")
  }

  const loadData = useCallback(async (pageIndex: number = 0, sortingState: SortingState = []) => {
    setLoading(true)
    try {
      const orderBy = sortingState && sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
      const res = await apiFetch(`/sessions/?skip=${pageIndex * 10}&limit=10${orderBy}`)
      const data = res?.data || res?.results || []
      const mapped = (data || []).map((s: any) => ({
        id: s.id,
        account_id: s.account_id,
        account: s.account ?? { number: s.account_number ?? null },
        ext_id: s.ext_id,
        msg_count: s.msg_count,
        status: s.status,
        created_at: s.created_at,
        updated_at: s.updated_at,
        info_1: s.info_1,
        info_2: s.info_2,
        info_3: s.info_3,
      }))
      setSessions(mapped)
    } catch (err) {
      console.error("Error loading sessions:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData(pageIndex, sorting)
  }, [loadData, pageIndex, sorting])

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

  if (loading) return <div className="p-4">Loading sessions...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>WA Sessions</CardTitle>
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
        <DataTable table={table}>
          <DataTableToolbar table={table}>
            <Button variant="outline" size="sm" onClick={() => loadData(table.getState().pagination.pageIndex, table.getState().sorting)}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}
