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
import { apiFetch } from "@/lib/api"
import { formatAccountStatus, formatAccountType } from "@/lib/enums"
import { DataTable } from "@/components/table/data-table"
import { DataTableToolbar } from "@/components/table/data-table-toolbar"

// Account type (API response)
export type Account = {
  id: number
  user_id: number
  user?: { name?: string }
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

// --- COLUMNS (без изменений кроме перевода на английский) ---
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

  columnHelper.accessor("number", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Number
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
  }),

  columnHelper.accessor("type", {
    header: "Type",
    cell: (info) => {
      const type = info.getValue() as number
      return <Badge variant={type === 1 ? "default" : "secondary"}>{formatAccountType(type)}</Badge>
    },
  }),

  columnHelper.accessor("user", {
    header: "User",
    cell: (info) => {
      const user = info.getValue() as any
      return <div>{user?.name ?? "-"}</div>
    },
  }),

  columnHelper.accessor("status", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Status
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const status = info.getValue() as number
      const mapped = formatAccountStatus(status)
      return <Badge variant={mapped.variant as any}>{mapped.label}</Badge>
    },
  }),

  columnHelper.accessor("session_count", { header: "Sessions" }),
  columnHelper.accessor("session_count", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Sessions
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
  }),
  columnHelper.accessor("created_at", {
    header: ({ column }) => (
      <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Created
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: (info) => {
      const v = info.getValue() as string
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
      const v = info.getValue() as string
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
          <DropdownMenuItem><Eye className="mr-2 h-4 w-4" /> View</DropdownMenuItem>
          <DropdownMenuItem><Edit className="mr-2 h-4 w-4" /> Edit</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive"><Trash2 className="mr-2 h-4 w-4" /> Delete</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
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
  const [pageIndex, setPageIndex] = useState(0)

  const buildOrderBy = (sorting: SortingState) => {
    return sorting
      .map((s) => (s.desc ? `-${s.id}` : `${s.id}`))
      .join("&order_by=")
  }

  const fetchAccounts = useCallback(async (pageIndex: number = 0, sortingState: SortingState = []) => {
    try {
      setLoading(true)
      const orderBy = sortingState && sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
      const res = await apiFetch(`/accounts/?skip=${pageIndex * 10}&limit=10${orderBy}`)
      setAccounts(res.data)
    } catch (err) {
      console.error("Failed to load accounts:", err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAccounts(pageIndex, sorting)
  }, [fetchAccounts, pageIndex, sorting])

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
    onStateChange: (updater) => {
      // updater can be function or state; normalize
      try {
        const s = typeof updater === 'function' ? updater({} as any) : updater
        const page = (s as any).pagination?.pageIndex ?? 0
        setPageIndex(page)
      } catch (e) {
        // ignore
      }
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

  if (loading) return <div className="p-4">Loading accounts...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>WA Accounts</CardTitle>
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
        <DataTable table={table}>
          <DataTableToolbar table={table}>
            <Button variant="outline" size="sm" onClick={() => fetchAccounts(table.getState().pagination.pageIndex, table.getState().sorting)}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}
