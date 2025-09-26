"use client"

import { useState, useEffect } from "react"
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
import { ArrowUpDown, MoreHorizontal, Eye, Edit, Trash2, Search, Download, Plus } from "lucide-react"

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

// тип данных сессии
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

// helper для колонок
const columnHelper = createColumnHelper<Session>()

// форматирование даты
const formatDate = (val: string | null) => {
  if (!val) return "-"
  return new Date(val).toLocaleString("ru-RU", {
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
        aria-label="Выбрать все"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Выберите строку"
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

  columnHelper.accessor("account_id", { header: "Account ID" }),
  columnHelper.accessor("ext_id", { header: "External ID" }),
  columnHelper.accessor("msg_count", { header: "Messages" }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => {
      const status = info.getValue()
      if (status === null) return <Badge variant="outline">Unknown</Badge>
      return (
        <Badge variant={status === 1 ? "default" : "destructive"}>
          {status === 1 ? "Active" : "Inactive"}
        </Badge>
      )
    },
  }),
  columnHelper.accessor("created_at", {
    header: "Created At",
    cell: (info) => formatDate(info.getValue()),
  }),
  columnHelper.accessor("updated_at", {
    header: "Updated At",
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
          <DropdownMenuLabel>Действия</DropdownMenuLabel>
          <DropdownMenuItem><Eye className="mr-2 h-4 w-4" /> Вид</DropdownMenuItem>
          <DropdownMenuItem><Edit className="mr-2 h-4 w-4" /> Редактировать</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive"><Trash2 className="mr-2 h-4 w-4" /> Удалить</DropdownMenuItem>
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

  useEffect(() => {
    setLoading(true)
    apiFetch("/sessions/")
      .then((res) => {
        // если API вернул { data: [...], total: N }
        setSessions(res?.data ?? [])
      })
      .catch((err) => console.error("Ошибка загрузки sessions:", err))
      .finally(() => setLoading(false))
  }, [])

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

  if (loading) return <div className="p-4">Загрузка сессий...</div>

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Sessions</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Экспорт
            </Button>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Добавить
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <Search className="w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Поиск..."
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
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center">Нет данных.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* пагинация */}
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-muted-foreground">
            Страница {table.getState().pagination.pageIndex + 1} из {table.getPageCount()}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Вперёд
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
