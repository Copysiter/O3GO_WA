import React, { useEffect, useState, useCallback, useMemo } from "react"
import {
  flexRender,
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
import { Button } from "./ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card"
import { Input } from "./ui/input"
import { Checkbox } from "./ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table"
import { SimpleFilterButton } from "./table/simple-filter-button"
import { AdvancedSortButton } from "./table/advanced-sort-button"
import { apiFetch } from "../lib/api"
import { RefreshCw, Plus, Search, Edit, Trash2, MoreHorizontal, Eye, ArrowUpDown } from "lucide-react"
import { UserForm } from "./forms/user-form"
import { type User } from "@/types/data-table"
import { useQueryState } from "nuqs"
import { getFiltersStateParser } from "@/lib/parsers"
import type { ExtendedColumnFilter } from "@/types/data-table"

const columnHelper = createColumnHelper<User>()

type ViewState = "list" | "create" | "edit"

export const UsersTable: React.FC = () => {
  const [data, setData] = useState<User[]>([])
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

  const [view, setView] = useState<ViewState>("list")
  const [currentUser, setCurrentUser] = useState<User | null>(null)

  const columnIds = ["id", "name", "login", "created_at"]
  const [advFilters] = useQueryState(
    "filters",
    getFiltersStateParser<User>(columnIds).withDefault([]),
  )

  const variantMap: Record<string, "text" | "number" | "range" | "date" | "dateRange" | "boolean" | "select" | "multiSelect"> = {
    id: "number",
    name: "text",
    login: "text",
    created_at: "date",
  }

  const buildFilterQuery = (filters: ExtendedColumnFilter<User>[]) => {
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

  const buildOrderBy = (sorting: SortingState) =>
    sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

  const fetchUsers = useCallback(
    async (
      page = 0,
      size = 10,
      sortingState: SortingState = [],
      filter = "",
      columnFiltersState: ColumnFiltersState = [],
    ) => {
      setLoading(true)
      try {
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const filtersBasic = columnFiltersState
          .map((f) => (f.value ? `&${encodeURIComponent(f.id)}__ilike=${encodeURIComponent(`%${String(f.value)}%`)}` : ""))
          .join("")
        const filtersAdvanced = buildFilterQuery(advFilters as ExtendedColumnFilter<User>[])
        const res = await apiFetch(
          `/users/?skip=${page * size}&limit=${size}${orderBy}${filtersBasic}${filtersAdvanced}`,
        )
        const result = res.data ?? res.items ?? res
        const count = res.total ?? result.length
        setData(Array.isArray(result) ? result : [])
        setTotal(count)
      } catch (e) {
        console.error(e)
        setData([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    [advFilters]
  )

  useEffect(() => {
    fetchUsers(pageIndex, pageSize, sorting, globalFilter, columnFilters)
  }, [fetchUsers, pageIndex, pageSize, sorting, globalFilter, columnFilters])

  const handleAdd = () => {
    setCurrentUser(null)
    setView("create")
  }

  const handleEdit = (user: User) => {
    setCurrentUser(user)
    setView("edit")
  }

  const handleDelete = async (user: User) => {
    if (!window.confirm(`Delete user ${user.name ?? user.id}?`)) return
    try {
      await apiFetch(`/users/${user.id}`, { method: "DELETE" })
      fetchUsers(pageIndex, pageSize, sorting, globalFilter)
    } catch (e) {
      console.error(e)
      window.alert("Failed to delete user")
    }
  }

  const handleSuccess = () => {
    setView("list")
    setCurrentUser(null)
    fetchUsers(pageIndex, pageSize, sorting, globalFilter)
  }

  const handleCancel = () => {
    setView("list")
    setCurrentUser(null)
  }

  const columns = useMemo(
    () => [
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
        enableSorting: true,
        enableColumnFilter: true,
        meta: { label: "ID", variant: "number", placeholder: "ID" },
      }),
      columnHelper.accessor("name", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Name
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        enableSorting: true,
        enableColumnFilter: true,
        meta: { label: "Name", variant: "text", placeholder: "Search name" },
      }),
      columnHelper.accessor("login", {
        header: ({ column }) => (
          <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
            Login
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        enableSorting: true,
        enableColumnFilter: true,
        meta: { label: "Login", variant: "text", placeholder: "Search login" },
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
        enableColumnFilter: true,
        meta: { label: "Created", variant: "date" },
      }),
      columnHelper.display({
        id: "actions",
        cell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => handleEdit(row.original)}>
                <Edit className="mr-2 h-4 w-4" /> Edit
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(row.original)}>
                <Trash2 className="mr-2 h-4 w-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      }),
    ],
    [handleEdit, handleDelete]
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

  if (view === "create" || view === "edit") {
    return <UserForm user={currentUser} onSuccess={handleSuccess} onCancel={handleCancel} />
  }

  if (loading) return <div className="p-4">Loading users...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Users</CardTitle>
          <Button variant="outline" size="sm" onClick={() => fetchUsers(pageIndex, pageSize, sorting, globalFilter, columnFilters)}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <SimpleFilterButton table={table} />
          <AdvancedSortButton table={table} />
          <Button onClick={handleAdd}>
            <Plus className="mr-2 h-4 w-4" /> Add
          </Button>
          <Search className="w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search users..."
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="max-w-sm"
          />
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
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-muted-foreground">
            {total > 0 ? (
              <>Showing {pageIndex * pageSize + 1} to {Math.min((pageIndex + 1) * pageSize, total)} of {total} results</>
            ) : (
              <>No results</>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Next
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default UsersTable
