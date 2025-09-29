import React, { useEffect, useState, useCallback } from "react"
import { useReactTable, createColumnHelper, getCoreRowModel, getPaginationRowModel, getSortedRowModel, getFilteredRowModel, type SortingState, type ColumnFiltersState, type VisibilityState } from "@tanstack/react-table"
import { Button } from "./ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card"
import { Input } from "./ui/input"
import { DataTable } from "./table/data-table"
import { DataTableToolbar } from "./table/data-table-toolbar"
import { apiFetch } from "../lib/api"
import { RefreshCw, Plus, Search, Edit, Trash2 } from "lucide-react"

type User = {
  id: number
  name?: string
  email?: string
  created_at?: string
}

const columnHelper = createColumnHelper<User>()

export const UsersTable: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = useState({})
  const [globalFilter, setGlobalFilter] = useState("")

  const [pageIndex, setPageIndex] = useState(0)

  const buildOrderBy = (sorting: SortingState) =>
    sorting.map((s) => (s.desc ? `-${s.id}` : `${s.id}`)).join("&order_by=")

  const fetchUsers = useCallback(async (page = 0, sortingState: SortingState = []) => {
    setLoading(true)
    try {
      const orderBy = sortingState && sortingState.length ? `&order_by=${buildOrderBy(sortingState)}` : ""
      const res = await apiFetch(`/users/?skip=${page * 10}&limit=10${orderBy}`)
      // support both { data: [...] } and direct array
      const data = res.data ?? res.items ?? res
      setUsers(data || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsers(pageIndex, sorting)
  }, [fetchUsers, pageIndex, sorting])

  const handleAdd = async () => {
    const name = window.prompt("User name")
    if (!name) return
    const email = window.prompt("Email (optional)")
    try {
      await apiFetch(`/users/`, { method: "POST", body: JSON.stringify({ name, email }) })
      fetchUsers(pageIndex)
    } catch (e) {
      console.error(e)
      window.alert("Failed to create user")
    }
  }

  const handleEdit = async (user: User) => {
    const name = window.prompt("User name", user.name ?? "")
    if (name === null) return
    const email = window.prompt("Email (optional)", user.email ?? "")
    try {
      await apiFetch(`/users/${user.id}`, { method: "PUT", body: JSON.stringify({ name, email }) })
      fetchUsers(pageIndex, sorting)
    } catch (e) {
      console.error(e)
      window.alert("Failed to update user")
    }
  }

  const handleDelete = async (user: User) => {
    if (!window.confirm(`Delete user ${user.name ?? user.id}?`)) return
    try {
      await apiFetch(`/users/${user.id}`, { method: "DELETE" })
      fetchUsers(pageIndex, sorting)
    } catch (e) {
      console.error(e)
      window.alert("Failed to delete user")
    }
  }

  const columns = [
    columnHelper.accessor("id", { header: "ID" }),
    columnHelper.accessor("name", { header: "Name" }),
    columnHelper.accessor("email", { header: "Email" }),
    columnHelper.accessor("created_at", {
      header: "Created",
      cell: (info) => {
        const v = info.getValue() as string
        return <div>{v ? new Date(v).toISOString().replace('T', ' ').substring(0, 19) : '-'}</div>
      },
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
  ]

  const table = useReactTable({
    data: users,
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
            <Button variant="outline" size="sm" onClick={() => fetchUsers(table.getState().pagination.pageIndex, table.getState().sorting)}>
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
