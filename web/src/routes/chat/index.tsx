import { useState, useRef, useEffect } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Send, Bot, User } from 'lucide-react'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/chat/')({
  component: ChatPage,
})

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

/**
 * AI 分析聊天页
 *
 * 使用 Vercel AI SDK 的 useChat hook 做流式消息展示。
 * 目前用 mock 流式响应占位，后续对接后端 /api/chat。
 */
function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '你好！我是 Fund Screener AI 助手。我可以帮你分析基金趋势、解读筛选结果、对比持仓相关性。你想聊什么？',
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    // TODO: 对接后端 /api/chat，使用 useChat 做真实流式响应
    // 目前 mock 一个延迟响应
    setTimeout(() => {
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `收到你的问题："${userMsg.content}"

这是一个占位回复。后续接入 Vercel AI SDK 的 \`useChat\` hook 后，这里会显示真实的 LLM 流式响应。

你可以问：
- "最近哪些基金趋势最强？"
- "帮我分析一下 QQQ 的持仓变化"
- "给我推荐几只低风险的高分红 ETF"`,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setIsLoading(false)
    }, 1200)
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">AI 分析</h2>
        <p className="text-sm text-muted-foreground">
          向 AI 助手提问，获取基金深度分析
        </p>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardHeader className="border-b py-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Bot className="h-4 w-4" />
            Fund Screener AI
          </CardTitle>
        </CardHeader>

        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  'flex gap-3',
                  msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                )}
              >
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  )}
                >
                  {msg.role === 'user' ? (
                    <User className="h-4 w-4" />
                  ) : (
                    <Bot className="h-4 w-4" />
                  )}
                </div>
                <div
                  className={cn(
                    'max-w-[80%] rounded-lg px-4 py-2 text-sm',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  )}
                >
                  <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-lg bg-muted px-4 py-2 text-sm text-muted-foreground">
                  思考中...
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <Separator />

        <CardContent className="p-4">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              placeholder="输入问题，例如：最近哪些基金趋势最强？"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1"
              disabled={isLoading}
            />
            <Button type="submit" size="icon" disabled={isLoading}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
