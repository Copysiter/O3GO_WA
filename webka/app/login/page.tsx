"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/access-token", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username,
          password,
        }),
      })

      if (!res.ok) {
        throw new Error("Неверный логин или пароль")
      }

      const data = await res.json()
      localStorage.setItem("token", data.access_token) // ⚡️ сохраняем токен
      window.location.href = "/" // редирект на главную страницу
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <form
        onSubmit={handleLogin}
        className="p-6 border rounded-lg bg-card shadow w-96 space-y-4"
      >
        <h1 className="text-xl font-bold">Вход</h1>

        <Input
          placeholder="Логин"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <Input
          placeholder="Пароль"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <div className="text-red-500 text-sm">{error}</div>}

        <Button type="submit" className="w-full">
          Войти
        </Button>
      </form>
    </div>
  )
}
