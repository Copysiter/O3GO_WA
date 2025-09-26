"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Menu, Search, Bell, Settings, Users, MessageSquare, Activity } from "lucide-react"
import { cn } from "@/lib/utils"
import { AccountsTable } from "./accounts-table"
import { MessagesTable } from "./messages-table"
import { SessionsLogsTable } from "./session-logs-table"
import { ThemeToggle } from "@/components/theme-toggle"

const sidebarItems = [
  { name: "Аккаунты", icon: Users },
  { name: "Сообщения", icon: MessageSquare },
  { name: "Данные по сессиям", icon: Activity },
]

interface DashboardLayoutProps {
  children?: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeItem, setActiveItem] = useState("Аккаунты")
  const [isMobile, setIsMobile] = useState(false)
  const [isAuth, setIsAuth] = useState<boolean | null>(null) // null = загрузка

  // Проверка токена при загрузке
  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) {
      setIsAuth(false)
      return
    }

    // Проверяем токен через API
// Проверяем токен через API
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/test-token`, {
      method: "POST", // ⚡ вместо GET
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.ok) {
          setIsAuth(true)
        } else {
          localStorage.removeItem("token")
          setIsAuth(false)
        }
      })
      .catch(() => {
        setIsAuth(false)
      })
  }, [])

  // Определяем мобильное устройство
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024)
    checkMobile()
    window.addEventListener("resize", checkMobile)
    return () => window.removeEventListener("resize", checkMobile)
  }, [])

  // Автоматически закрываем сайдбар на мобильных
  useEffect(() => {
    setSidebarOpen(!isMobile)
  }, [isMobile])

  const renderContent = () => {
    switch (activeItem) {
      case "Аккаунты":
        return <AccountsTable />
      case "Сообщения":
        return <MessagesTable />
      case "Данные по сессиям":
        return <SessionsLogsTable />
      default:
        return children || <AccountsTable />
    }
  }

  // Форма логина
  if (isAuth === false) {
    window.location.href = "/login"
    return null
  }
  
  // Пока проверяем токен → спиннер
  if (isAuth === null) {
    return (
      <div className="flex h-screen items-center justify-center">
        <span className="text-lg">Загрузка...</span>
      </div>
    )
  }


  // Авторизованный UI
  return (
    <div className="min-h-screen bg-background">
      {/* Topbar */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
        <div className="flex h-14 items-center px-4 sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="mr-2 lg:hidden"
          >
            <Menu className="h-4 w-4" />
          </Button>

          <div className="flex-1 flex items-center space-x-4">
            <h1 className="text-lg font-semibold hidden sm:block">AltronV2</h1>
          </div>

          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="icon" className="hidden sm:flex">
              <Bell className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="hidden sm:flex">
              <Settings className="h-4 w-4" />
            </Button>

            <ThemeToggle />

            <Button
              variant="ghost"
              onClick={() => {
                localStorage.removeItem("token")
                setIsAuth(false)
              }}
            >
              Выйти
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={cn(
            "fixed lg:sticky top-14 h-[calc(100vh-3.5rem)] border-r bg-sidebar transition-all duration-300 z-40",
            sidebarOpen ? "w-64 left-0" : "-left-64 lg:left-0 lg:w-16"
          )}
        >
          <nav className="flex flex-col p-4 space-y-2">
            {sidebarItems.map((item) => {
              const Icon = item.icon
              return (
                <Button
                  key={item.name}
                  variant={activeItem === item.name ? "secondary" : "ghost"}
                  className={cn("justify-start", !sidebarOpen && "px-2")}
                  onClick={() => {
                    setActiveItem(item.name)
                    if (isMobile) setSidebarOpen(false)
                  }}
                >
                  <Icon className="h-4 w-4" />
                  {sidebarOpen && <span className="ml-2">{item.name}</span>}
                </Button>
              )
            })}
          </nav>
        </aside>

        {/* Overlay для мобильных */}
        {isMobile && sidebarOpen && (
          <div
            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          <div className="border-b bg-muted/40 px-4 lg:px-6 py-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">{activeItem}</h2>
              <div className="text-sm text-muted-foreground hidden sm:block">
                Последнее обновление: {new Date().toLocaleString()}
              </div>
            </div>
          </div>

          <div className="p-4 lg:p-6">{renderContent()}</div>
        </main>
      </div>
    </div>
  )
}
