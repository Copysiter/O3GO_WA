"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { toast } from "@/components/ui/use-toast"
import { useState, useEffect } from "react"
import { apiFetch } from "@/lib/api"

// Схема валидации формы
const userFormSchema = z.object({
  name: z.string().min(2, {
    message: "Name must be at least 2 characters.",
  }),
  login: z.string().min(1, { message: "Login is required." }),
  password: z.string().optional(),
})

type UserFormValues = z.infer<typeof userFormSchema>

// Начальные значения формы
const defaultValues: Partial<UserFormValues> = {
  name: "",
  login: "",
}

interface UserFormProps {
  onSuccess?: () => void
  onCancel?: () => void
  user?: {
    id: number
    name: string
    login?: string
  } | null
}

export function UserForm({ onSuccess, onCancel, user }: UserFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const isEditing = Boolean(user)

  const form = useForm<UserFormValues>({
    resolver: zodResolver(userFormSchema),
    defaultValues: user
      ? {
          name: user.name,
          login: user.login ?? "",
        }
      : defaultValues,
  })

  useEffect(() => {
    if (user) {
      form.reset({
        name: user.name,
        login: user.login,
      })
    } else {
      form.reset(defaultValues)
    }
  }, [form, user])

  async function onSubmit(data: UserFormValues) {
    setIsLoading(true)
    try {
      if (isEditing && user) {
        await apiFetch(`/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        })

        toast({
          title: "Success",
          description: "User updated successfully.",
        })
      } else {
        await apiFetch("/users/", {
          method: "POST",
          body: JSON.stringify(data),
        })

        toast({
          title: "Success",
          description: "User created successfully.",
        })
      }

      form.reset()
      onSuccess?.()
    } catch (error) {
      toast({
        title: "Error",
        description: `Failed to ${isEditing ? "update" : "create"} user. Please try again.`,
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const FormBody = (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input placeholder="Enter name" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="login"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Login</FormLabel>
              <FormControl>
                <Input placeholder="Enter login" {...field} disabled={isLoading} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {!isEditing && (
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input type="password" placeholder="Enter password" {...field} disabled={isLoading} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <div className="flex items-center justify-end gap-2">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
              Cancel
            </Button>
          )}
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Saving..." : isEditing ? "Save" : "Create"}
          </Button>
        </div>
      </form>
    </Form>
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>{isEditing ? "Edit user" : "Create new user"}</CardTitle>
        <CardDescription>
          {isEditing ? "Edit the user details." : "Add a new user to the system. Fill required fields."}
        </CardDescription>
      </CardHeader>
      <CardContent>{FormBody}</CardContent>
    </Card>
  )
}