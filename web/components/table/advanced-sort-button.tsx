"use client"

import type { Table, Column } from "@tanstack/react-table"
import { ArrowUpDown, Trash2, GripVertical } from "lucide-react"
import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { dataTableConfig } from "@/config/data-table"

interface AdvancedSortButtonProps<TData> {
  table: Table<TData>
}

export function AdvancedSortButton<TData>({
  table,
}: AdvancedSortButtonProps<TData>) {
  const [open, setOpen] = React.useState(false)
  
  const sorting = table.getState().sorting
  const setSorting = table.setSorting

  const sortableColumns = React.useMemo(() => {
    return table.getAllColumns().filter((column) => column.getCanSort())
  }, [table])

  const columnLabels = React.useMemo(() => {
    const labels = new Map<string, string>()
    for (const column of sortableColumns) {
      labels.set(column.id, column.columnDef.meta?.label ?? column.id)
    }
    return labels
  }, [sortableColumns])

  const availableColumns = React.useMemo(() => {
    const sortingIds = new Set(sorting.map((s) => s.id))
    return sortableColumns.filter((col) => !sortingIds.has(col.id))
  }, [sortableColumns, sorting])

  const onSortAdd = () => {
    const firstColumn = availableColumns[0]
    if (!firstColumn) return

    setSorting([...sorting, { id: firstColumn.id, desc: false }])
  }

  const onSortUpdate = (sortId: string, updates: { id?: string; desc?: boolean }) => {
    setSorting((prev) =>
      prev.map((sort) =>
        sort.id === sortId ? { ...sort, ...updates } : sort
      )
    )
  }

  const onSortRemove = (sortId: string) => {
    setSorting((prev) => prev.filter((item) => item.id !== sortId))
  }

  const onSortingReset = () => {
    setSorting([])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          <ArrowUpDown className="mr-2 h-4 w-4" />
          Sort
          {sorting.length > 0 && (
            <Badge
              variant="secondary"
              className="ml-2 h-[18px] rounded-sm px-1 font-mono text-[10px]"
            >
              {sorting.length}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[380px] p-4" align="start">
        <div className="flex flex-col gap-3.5">
          <div className="flex flex-col gap-1">
            <h4 className="font-medium leading-none">
              {sorting.length > 0 ? "Sort by" : "No sorting applied"}
            </h4>
            <p className="text-sm text-muted-foreground">
              {sorting.length > 0
                ? "Modify sorting to organize your rows."
                : "Add sorting to organize your rows."}
            </p>
          </div>

          {sorting.length > 0 && (
            <div className="flex max-h-[300px] flex-col gap-2 overflow-y-auto">
              {sorting.map((sort, index) => (
                <SortItem
                  key={sort.id}
                  sort={sort}
                  availableColumns={availableColumns}
                  columnLabels={columnLabels}
                  onSortUpdate={onSortUpdate}
                  onSortRemove={onSortRemove}
                />
              ))}
            </div>
          )}

          <div className="flex w-full items-center gap-2">
            <Button
              size="sm"
              className="rounded"
              onClick={onSortAdd}
              disabled={availableColumns.length === 0}
            >
              Add sort
            </Button>
            {sorting.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="rounded"
                onClick={onSortingReset}
              >
                Reset sorting
              </Button>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

interface SortItemProps<TData = any> {
  sort: { id: string; desc: boolean }
  availableColumns: Column<TData>[]
  columnLabels: Map<string, string>
  onSortUpdate: (sortId: string, updates: { id?: string; desc?: boolean }) => void
  onSortRemove: (sortId: string) => void
}

function SortItem({
  sort,
  availableColumns,
  columnLabels,
  onSortUpdate,
  onSortRemove,
}: SortItemProps) {
  const allColumns = React.useMemo(() => {
    const current = { id: sort.id, label: columnLabels.get(sort.id) ?? sort.id }
    const available = availableColumns.map((col) => ({
      id: col.id,
      label: columnLabels.get(col.id) ?? col.id,
    }))
    return [current, ...available]
  }, [sort.id, availableColumns, columnLabels])

  return (
    <div className="flex items-center gap-2">
      <Select
        value={sort.id}
        onValueChange={(value) => onSortUpdate(sort.id, { id: value })}
      >
        <SelectTrigger className="h-8 w-44 rounded">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {allColumns.map((column) => (
            <SelectItem key={column.id} value={column.id}>
              {column.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={sort.desc ? "desc" : "asc"}
        onValueChange={(value) =>
          onSortUpdate(sort.id, { desc: value === "desc" })
        }
      >
        <SelectTrigger className="h-8 w-24 rounded">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {dataTableConfig.sortOrders.map((order) => (
            <SelectItem key={order.value} value={order.value}>
              {order.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        variant="outline"
        size="icon"
        className="size-8 shrink-0 rounded"
        onClick={() => onSortRemove(sort.id)}
      >
        <Trash2 className="size-4" />
      </Button>

      <Button
        variant="outline"
        size="icon"
        className="size-8 shrink-0 rounded cursor-move"
      >
        <GripVertical className="size-4" />
      </Button>
    </div>
  )
}

