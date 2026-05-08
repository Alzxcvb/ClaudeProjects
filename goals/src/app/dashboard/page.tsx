'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type { Goal, Habit, HabitLog } from '@/types'
import Skeleton from '@/components/Skeleton'

interface GoalWithNote {
  id: string
  title: string
  emoji: string
}

export default function DashboardPage() {
  const router = useRouter()
  const [goals, setGoals] = useState<Goal[]>([])
  const [allGoals, setAllGoals] = useState<GoalWithNote[]>([])
  const [logs, setLogs] = useState<Record<string, HabitLog>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [milestones, setMilestones] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [today] = useState(new Date().toISOString().split('T')[0])
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        // Fetch goals and habits for selectedDate
        const goalsResponse = await fetch('/api/goals')
        const goalsData = await goalsResponse.json()
        setGoals(goalsData)

        // Fetch habit logs for selectedDate
        const logsResponse = await fetch(`/api/habits/${selectedDate}`)
        const logsData = await logsResponse.json()

        const logsMap: Record<string, HabitLog> = {}
        logsData.forEach((log: HabitLog) => {
          logsMap[log.habitId] = log
        })
        setLogs(logsMap)

        // Fetch all goals for note creation
        const allGoalsResponse = await fetch('/api/goals?all=true')
        if (allGoalsResponse.ok) {
          const allGoalsData = await allGoalsResponse.json()
          setAllGoals(allGoalsData)
        } else {
          setAllGoals(goalsData)
        }
      } catch (error) {
        console.error('Failed to fetch data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [selectedDate])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return

      if (e.key === 'ArrowLeft') {
        const [y, m, d] = selectedDate.split('-').map(Number)
        const prev = new Date(Date.UTC(y, m - 1, d - 1))
        setSelectedDate(prev.toISOString().split('T')[0])
      } else if (e.key === 'ArrowRight') {
        const [y, m, d] = selectedDate.split('-').map(Number)
        const next = new Date(Date.UTC(y, m - 1, d + 1))
        const nextStr = next.toISOString().split('T')[0]
        if (nextStr <= today) setSelectedDate(nextStr)
      } else if (e.key === 't' || e.key === 'T') {
        setSelectedDate(today)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedDate, today])

  const handleHabitToggle = async (habitId: string) => {
    const currentLog = logs[habitId]
    const newCompleted = !currentLog?.completed

    try {
      const response = await fetch(`/api/habits/${selectedDate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          habitId,
          completed: newCompleted,
          value: currentLog?.value,
        }),
      })

      if (response.ok) {
        const newLog = await response.json()
        setLogs((prev) => ({
          ...prev,
          [habitId]: newLog,
        }))
      }
    } catch (error) {
      console.error('Failed to save habit:', error)
    }
  }

  const handleHabitValue = async (habitId: string, value?: number) => {
    const currentLog = logs[habitId]

    try {
      const response = await fetch(`/api/habits/${selectedDate}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          habitId,
          completed: currentLog?.completed || false,
          value,
        }),
      })

      if (response.ok) {
        const newLog = await response.json()
        setLogs((prev) => ({
          ...prev,
          [habitId]: newLog,
        }))
      }
    } catch (error) {
      console.error('Failed to save habit value:', error)
    }
  }

  const handleAddNote = async (goalId: string) => {
    const content = notes[goalId]
    if (!content?.trim()) return

    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goalId,
          content,
          milestone: milestones[goalId] || false,
          date: selectedDate,
        }),
      })

      if (response.ok) {
        setNotes((prev) => ({
          ...prev,
          [goalId]: '',
        }))
        setMilestones((prev) => ({
          ...prev,
          [goalId]: false,
        }))
      }
    } catch (error) {
      console.error('Failed to add note:', error)
    }
  }

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.push('/login')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <Skeleton lines={5} />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <h1 className="text-4xl font-bold text-white">
              {selectedDate === today ? 'Today' : selectedDate}
            </h1>
            <input
              type="date"
              value={selectedDate}
              max={today}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-100 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={() => setSelectedDate(today)}
              disabled={selectedDate === today}
              className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed rounded-lg text-zinc-100 text-sm transition-colors"
            >
              Today
            </button>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard/goals"
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-100 text-sm transition-colors"
            >
              Manage Goals
            </Link>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-100 text-sm transition-colors"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="space-y-8">
          {goals.map((goal) => (
            <div
              key={goal.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-6"
            >
              <div className="flex items-center gap-3 mb-6">
                <span className="text-3xl">{goal.emoji}</span>
                <h2 className="text-2xl font-bold text-white">{goal.title}</h2>
              </div>

              {goal.habits.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-zinc-400 uppercase mb-3">
                    Habits
                  </h3>
                  <div className="space-y-3">
                    {goal.habits.map((habit) => {
                      const log = logs[habit.id]
                      const isQuantifiable =
                        habit.name.includes('Pages') ||
                        habit.name.includes('Sleep') ||
                        habit.name.includes('Hours') ||
                        habit.name.includes('Posts') ||
                        habit.name.includes('Tokens')

                      return (
                        <div
                          key={habit.id}
                          className="flex items-center justify-between bg-zinc-800 px-4 py-3 rounded"
                        >
                          <label className="flex items-center gap-3 flex-1 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={log?.completed || false}
                              onChange={() => handleHabitToggle(habit.id)}
                              className="w-5 h-5 rounded border-zinc-600 bg-zinc-700 accent-blue-500"
                            />
                            <span className="text-zinc-100">{habit.name}</span>
                          </label>
                          {isQuantifiable && (
                            <input
                              type="number"
                              value={log?.value || ''}
                              onChange={(e) =>
                                handleHabitValue(
                                  habit.id,
                                  e.target.value ? parseFloat(e.target.value) : undefined
                                )
                              }
                              placeholder="0"
                              className="w-20 px-2 py-1 bg-zinc-700 border border-zinc-600 rounded text-white text-sm text-right"
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              <div className="border-t border-zinc-800 pt-4">
                <h3 className="text-sm font-semibold text-zinc-400 uppercase mb-3">
                  Add Note
                </h3>
                <div className="space-y-2">
                  <textarea
                    value={notes[goal.id] || ''}
                    onChange={(e) =>
                      setNotes((prev) => ({
                        ...prev,
                        [goal.id]: e.target.value,
                      }))
                    }
                    placeholder="Add a note or milestone..."
                    className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-none"
                    rows={2}
                  />
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={milestones[goal.id] || false}
                        onChange={(e) =>
                          setMilestones((prev) => ({
                            ...prev,
                            [goal.id]: e.target.checked,
                          }))
                        }
                        className="w-4 h-4 rounded border-zinc-600 bg-zinc-700 accent-amber-500"
                      />
                      <span className="text-sm text-zinc-400">Milestone</span>
                    </label>
                    <button
                      onClick={() => handleAddNote(goal.id)}
                      disabled={!notes[goal.id]?.trim()}
                      className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm rounded transition-colors"
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
