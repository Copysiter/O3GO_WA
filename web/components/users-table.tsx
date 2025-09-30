import React, { useEffect, useState, useCallback, useMemo } from "react"
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
import { Button } from "./ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card"
import { Input } from "./ui/input"
import { DataTable } from "./table/data-table"
import { DataTableToolbar } from "./table/data-table-toolbar"
import { apiFetch } from "../lib/api"
import { RefreshCw, Plus, Search, Edit, Trash2 } from "lucide-react"
import { UserForm } from "./forms/user-form"
import { type User } from "@/types/data-table"

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

  const buildOrderBy = (sorting: SortingState) =>
    sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join(",")

  const fetchUsers = useCallback(
    async (page = 0, size = 10, sortingState: SortingState = [], filter = "") => {
      setLoading(true)
      try {
        const orderBy = sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
        const search = filter ? `&q=${filter}` : ""
        const res = await apiFetch(`/users/?skip=${page * size}&limit=${size}${orderBy}${search}`)
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
    []
  )

  useEffect(() => {
    fetchUsers(pageIndex, pageSize, sorting, globalFilter)
  }, [fetchUsers, pageIndex, pageSize, sorting, globalFilter])

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
      columnHelper.accessor("id", { header: "ID" }),
      columnHelper.accessor("name", { header: "Name" }),
      columnHelper.accessor("login", { header: "Login" }),
      columnHelper.accessor("created_at", {
        header: "Created",
        cell: (info) => {
          const v = info.getValue()
          return <div>{v ? new Date(v).toISOString().replace("T", " ").substring(0, 19) : "-"}</div>
        },
        enableSorting: true,
      }),
      columnHelper.display({
        id: "actions",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Button size="icon" variant="ghost" onClick={() => handleEdit(row.original)}>
              <Edit className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" onClick={() => handleDelete(row.original)}>
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
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

  if (view === "create" || view === "edit") {
    return <UserForm user={currentUser} onSuccess={handleSuccess} onCancel={handleCancel} />
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Users</CardTitle>
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
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
              onClick={() => fetchUsers(pageIndex, pageSize, sorting, globalFilter)}
            >
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
            <Button onClick={handleAdd}>
              <Plus className="mr-2 h-4 w-4" /> Add
            </Button>
          </DataTableToolbar>
        </DataTable>
      </CardContent>
    </Card>
  )
}

export default UsersTable
