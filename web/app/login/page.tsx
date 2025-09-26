"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { apiFetch } from "@/lib/api"

export default function LoginPage() {
  const router = useRouter()
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      // здесь токен получаем напрямую, без автоматического Authorization
      const res = await fetch("http://localhost:8000/api/v1/auth/access-token", {
        method: "POST",
        body: new URLSearchParams({
          username: login,
          password: password,
        }),
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }).then((r) => r.json())

      if (res.access_token) {
        localStorage.setItem("token", res.access_token) // единый ключ
        router.push("/") // редирект на главную
      } else {
        setError("Неверный логин или пароль")
      }
    } catch (err) {
      setError("Ошибка авторизации")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-black text-white">
      <Card className="w-full max-w-sm border border-white/30 bg-black text-white">
        <CardHeader>
          <CardTitle className="text-center text-xl">Авторизация</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="login">Логин</Label>
              <Input
                id="login"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                placeholder="Введите логин"
                className="bg-black text-white border-white"
              />
            </div>
            <div>
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Введите пароль"
                className="bg-black text-white border-white"
              />
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Входим..." : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
