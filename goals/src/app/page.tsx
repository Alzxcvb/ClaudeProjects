'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import type { Goal, HabitLog } from '@/types'
import EmptyState from '@/components/EmptyState'

function getStreak(logs: HabitLog[]): number {
  if (!logs.length) return 0

  let streak = 0
  const today = new Date()
  let currentDate = new Date(today)

  for (let i = 0; i < 365; i++) {
    const dateStr = currentDate.toISOString().split('T')[0]
    const log = logs.find((l) => l.date === dateStr && l.completed)

    if (log) {
      streak++
    } else if (currentDate.getTime() !== today.getTime()) {
      break
    }

    currentDate = new Date(currentDate.getTime() - 24 * 60 * 60 * 1000)
  }

  return streak
}

function getCompletionRate(logs: HabitLog[]): number {
  const last7Days = logs.slice(0, 7)
  if (!last7Days.length) return 0
  const completed = last7Days.filter((l) => l.completed).length
  return Math.round((completed / last7Days.length) * 100)
}

export default function Home() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchGoals = async () => {
      try {
        const response = await fetch('/api/goals')
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const data = await response.json()
        setGoals(Array.isArray(data) ? data : [])
      } catch (error) {
        console.error('Failed to fetch goals:', error)
        setGoals([])
      } finally {
        setLoading(false)
      }
    }

    fetchGoals()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-400">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-12">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Goals</h1>
            <p className="text-zinc-400">Track progress on what matters</p>
          </div>
          <Link
            href="/login"
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-100 text-sm transition-colors"
          >
            Login
          </Link>
        </div>

        <div className="space-y-8">
          {goals.length === 0 && (
            <EmptyState
              title="No active goals"
              description="Add goals from the dashboard to see them here."
              icon="🎯"
            />
          )}
          {goals.map((goal) => (
            <div
              key={goal.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-6"
            >
              <div className="flex items-start gap-4 mb-4">
                <span className="text-3xl">{goal.emoji}</span>
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-white">{goal.title}</h2>
                  <p className="text-zinc-400 mt-1">{goal.description}</p>
                </div>
              </div>

              {goal.habits.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-zinc-400 uppercase mb-3">
                    Habits
                  </h3>
                  <div className="space-y-2">
                    {goal.habits.map((habit) => {
                      const streak = getStreak(habit.logs ?? [])
                      const rate = getCompletionRate(habit.logs ?? [])

                      return (
                        <div
                          key={habit.id}
                          className="flex items-center justify-between bg-zinc-800 px-4 py-3 rounded"
                        >
                          <span className="text-zinc-100">{habit.name}</span>
                          <div className="flex items-center gap-4 text-sm">
                            <span className="text-zinc-400">
                              {streak} day streak
                            </span>
                            <span className="text-zinc-300">
                              {rate}% (7d)
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {(goal.notes?.length ?? 0) > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-zinc-400 uppercase mb-3">
                    Recent
                  </h3>
                  <div className="space-y-2">
                    {goal.notes?.map((note) => (
                      <div
                        key={note.id}
                        className={`px-4 py-3 rounded text-sm ${
                          note.milestone
                            ? 'bg-amber-500/10 border border-amber-500/20 text-amber-100'
                            : 'bg-zinc-800 text-zinc-100'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <p>{note.content}</p>
                          <span className="text-zinc-500 text-xs ml-2">
                            {new Date(note.date).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
