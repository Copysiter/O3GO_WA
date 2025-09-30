"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import {
  useReactTable,
  createColumnHelper,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
  type PaginationState,
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

export function AccountsTable() {
  const [data, setData] = useState<Account[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")
  const [{ pageIndex, pageSize }, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  const buildOrderBy = (sorting: SortingState) =>
    sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

  const fetchAccounts = useCallback(
    async (page = 0, size = 10, sortingState: SortingState = [], filter = "") => {
      setLoading(true)
      try {
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const search = filter ? `&q=${filter}` : ""
        const res = await apiFetch(`/accounts/?skip=${page * size}&limit=${size}${orderBy}${search}`)
        const result = res.data ?? res.items ?? res
        const count = res.total ?? result.length
        setData(Array.isArray(result) ? result : [])
        setTotal(count)
      } catch (err) {
        console.error("Failed to load accounts:", err)
        setData([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    fetchAccounts(pageIndex, pageSize, sorting, globalFilter)
  }, [fetchAccounts, pageIndex, pageSize, sorting, globalFilter])

  const columns = useMemo(
    () => [
      columnHelper.accessor("id", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            ID
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: (info) => <div className="font-medium">{info.getValue()}</div>,
        enableSorting: true,
      }),

      columnHelper.accessor("number", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Number
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        enableSorting: true,
      }),

      columnHelper.accessor("type", {
        header: "Type",
        cell: (info) => {
          const type = info.getValue()
          return <Badge variant={type === 1 ? "default" : "secondary"}>{formatAccountType(type)}</Badge>
        },
      }),

      columnHelper.accessor("user", {
        header: "User",
        cell: (info) => {
          const user = info.getValue()
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
          const status = info.getValue()
          const mapped = formatAccountStatus(status)
          return <Badge variant={mapped.variant as any}>{mapped.label}</Badge>
        },
        enableSorting: true,
      }),

      columnHelper.accessor("session_count", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Sessions
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        enableSorting: true,
      }),

      columnHelper.accessor("created_at", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Created
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: (info) => {
          const v = info.getValue()
          return <div>{v ? new Date(v).toISOString().replace("T", " ").substring(0, 19) : "-"}</div>
        },
        enableSorting: true,
      }),

      columnHelper.accessor("updated_at", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Updated
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: (info) => {
          const v = info.getValue()
          return <div>{v ? new Date(v).toISOString().replace("T", " ").substring(0, 19) : "-"}</div>
        },
        enableSorting: true,
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
    ],
    []
  )

  const table = useReactTable({
    data,
    columns,
    pageCount: Math.ceil(total / pageSize),
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      globalFilter,
      pagination: { pageIndex, pageSize },
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
  })

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
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchAccounts(pageIndex, pageSize, sorting, globalFilter)}
            >
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}
