"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface SortableContextValue<T> {
  value: T[]
  onValueChange: (value: T[]) => void
  getItemValue: (item: T) => string
}

const SortableContext = React.createContext<SortableContextValue<any> | null>(null)

function useSortableContext<T>() {
  const context = React.useContext(SortableContext) as SortableContextValue<T> | null
  if (!context) {
    throw new Error("Sortable components must be used within a Sortable provider")
  }
  return context
}

interface SortableProps<T> extends React.ComponentPropsWithoutRef<"div"> {
  value: T[]
  onValueChange: (value: T[]) => void
  getItemValue: (item: T) => string
}

export function Sortable<T>({
  value,
  onValueChange,
  getItemValue,
  children,
  className,
  ...props
}: SortableProps<T>) {
  return (
    <SortableContext.Provider value={{ value, onValueChange, getItemValue }}>
      <div className={cn("relative", className)} {...props}>
        {children}
      </div>
    </SortableContext.Provider>
  )
}

interface SortableContentProps extends React.ComponentPropsWithoutRef<"div"> {
  asChild?: boolean
}

export function SortableContent({
  asChild = false,
  children,
  className,
  ...props
}: SortableContentProps) {
  const Comp = asChild ? React.Fragment : "div"
  
  if (asChild) {
    return <>{children}</>
  }

  return (
    <Comp className={className} {...props}>
      {children}
    </Comp>
  )
}

interface SortableItemProps extends React.ComponentPropsWithoutRef<"div"> {
  value: string
  asChild?: boolean
}

export function SortableItem({
  value: _value,
  asChild = false,
  children,
  className,
  ...props
}: SortableItemProps) {
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...props,
      className: cn(children.props.className, className),
    } as any)
  }

  return (
    <div className={className} {...props}>
      {children}
    </div>
  )
}

interface SortableItemHandleProps extends React.ComponentPropsWithoutRef<"button"> {
  asChild?: boolean
}

export function SortableItemHandle({
  asChild = false,
  children,
  className,
  ...props
}: SortableItemHandleProps) {
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children, {
      ...props,
      className: cn(children.props.className, className),
    } as any)
  }

  return (
    <button type="button" className={className} {...props}>
      {children}
    </button>
  )
}

interface SortableOverlayProps extends React.ComponentPropsWithoutRef<"div"> {}

export function SortableOverlay({ children, className, ...props }: SortableOverlayProps) {
  return (
    <div className={cn("sr-only", className)} {...props}>
      {children}
    </div>
  )
}

