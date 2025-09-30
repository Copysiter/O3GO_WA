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
import { DataTable } from "@/components/table/data-table"
import { DataTableToolbar } from "@/components/table/data-table-toolbar"
import { apiFetch } from "@/lib/api"
import { formatMessageStatus } from "@/lib/enums"
import { getGeoFromPhoneNumber } from "@/lib/phone"

export type Message = {
  id: number | string
  dst_addr: string
  geo: string
  text: string
  status: number
  created_at: string | null
  sent_at: string | null
  updated_at: string | null
}

const columnHelper = createColumnHelper<Message>()

export function MessagesTable() {
  const [data, setData] = useState<Message[]>([])
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

  const fetchMessages = useCallback(
    async (page = 0, size = 10, sortingState: SortingState = [], filter = "") => {
      setLoading(true)
      try {
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const search = filter ? `&q=${filter}` : ""
        const res = await apiFetch(`/messages/?skip=${page * size}&limit=${size}${orderBy}${search}`)
        const result = res.data ?? res.items ?? res
        const count = res.total ?? result.length

        const mapped = (Array.isArray(result) ? result : []).map((msg: any) => ({
          ...msg,
          geo: getGeoFromPhoneNumber(msg.dst_addr),
        }))

        setData(mapped)
        setTotal(count)
      } catch (err) {
        console.error("Failed to load messages:", err)
        setData([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    fetchMessages(pageIndex, pageSize, sorting, globalFilter)
  }, [fetchMessages, pageIndex, pageSize, sorting, globalFilter])

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

      columnHelper.accessor("dst_addr", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Number
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        enableSorting: true,
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
          const formatted = formatMessageStatus(status)
          return (
            <Badge
              variant={
                status === 2 ? "default" : status < 1 ? "secondary" : "destructive"
              }
            >
              {formatted}
            </Badge>
          )
        },
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
      columnHelper.accessor("sent_at", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Sent
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchMessages(pageIndex, pageSize, sorting, globalFilter)}
            >
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}
