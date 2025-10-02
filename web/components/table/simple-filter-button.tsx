"use client"

import type { Table } from "@tanstack/react-table"
import { ListFilter } from "lucide-react"
import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"

interface SimpleFilterButtonProps<TData> {
  table: Table<TData>
}

export function SimpleFilterButton<TData>({
  table,
}: SimpleFilterButtonProps<TData>) {
  const [open, setOpen] = React.useState(false)
  
  const filterableColumns = React.useMemo(
    () => table.getAllColumns().filter((column) => column.getCanFilter()),
    [table]
  )

  const activeFilters = table.getState().columnFilters.length

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <ListFilter className="mr-2 h-4 w-4" />
          Filters
          {activeFilters > 0 && (
            <Badge
              variant="secondary"
              className="ml-2 h-[18px] rounded-sm px-1 font-mono text-[10px]"
            >
              {activeFilters}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[200px]">
        <DropdownMenuLabel>Toggle filters</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {filterableColumns.length === 0 ? (
          <div className="px-2 py-4 text-sm text-muted-foreground text-center">
            No filterable columns
          </div>
        ) : (
          filterableColumns.map((column) => {
            const isFiltered = table.getState().columnFilters.some(
              (filter) => filter.id === column.id
            )
            return (
              <DropdownMenuCheckboxItem
                key={column.id}
                checked={isFiltered}
                onCheckedChange={(value) => {
                  if (value) {
                    column.setFilterValue("")
                  } else {
                    column.setFilterValue(undefined)
                  }
                }}
              >
                {column.columnDef.meta?.label ?? column.id}
              </DropdownMenuCheckboxItem>
            )
          })
        )}
        {activeFilters > 0 && (
          <>
            <DropdownMenuSeparator />
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => {
                table.resetColumnFilters()
                setOpen(false)
              }}
            >
              Clear filters
            </Button>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

