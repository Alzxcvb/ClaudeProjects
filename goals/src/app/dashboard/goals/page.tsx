'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface Goal {
  id: string
  title: string
  emoji: string
  description: string
  status: 'ACTIVE' | 'ON_DECK' | 'ARCHIVED'
  order: number
}

export default function GoalsManagementPage() {
  const router = useRouter()
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAllGoals = async () => {
      try {
        // Fetch all goals including on-deck and archived
        const response = await fetch('/api/goals?all=true')
        if (response.ok) {
          const data = await response.json()
          setGoals(data)
        }
      } catch (error) {
        console.error('Failed to fetch goals:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchAllGoals()
  }, [])

  const handleStatusChange = async (goalId: string, newStatus: Goal['status']) => {
    try {
      const goal = goals.find((g) => g.id === goalId)
      if (!goal) return

      const response = await fetch('/api/goals', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: goalId,
          title: goal.title,
          description: goal.description,
          emoji: goal.emoji,
          status: newStatus,
          order: goal.order,
        }),
      })

      if (response.ok) {
        setGoals((prev) =>
          prev.map((g) =>
            g.id === goalId ? { ...g, status: newStatus } : g
          )
        )
      }
    } catch (error) {
      console.error('Failed to update goal status:', error)
    }
  }

  const handleMoveUp = async (goalId: string) => {
    const goal = goals.find((g) => g.id === goalId)
    if (!goal || goal.order === 0) return

    const otherGoal = goals.find(
      (g) => g.order === goal.order - 1 && g.status === goal.status
    )
    if (!otherGoal) return

    try {
      await Promise.all([
        fetch('/api/goals', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...goal,
            order: goal.order - 1,
          }),
        }),
        fetch('/api/goals', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...otherGoal,
            order: otherGoal.order + 1,
          }),
        }),
      ])

      setGoals((prev) =>
        prev.map((g) => {
          if (g.id === goalId) return { ...g, order: goal.order - 1 }
          if (g.id === otherGoal.id) return { ...g, order: otherGoal.order + 1 }
          return g
        })
      )
    } catch (error) {
      console.error('Failed to reorder goals:', error)
    }
  }

  const handleMoveDown = async (goalId: string) => {
    const goal = goals.find((g) => g.id === goalId)
    if (!goal) return

    const otherGoal = goals.find(
      (g) => g.order === goal.order + 1 && g.status === goal.status
    )
    if (!otherGoal) return

    try {
      await Promise.all([
        fetch('/api/goals', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...goal,
            order: goal.order + 1,
          }),
        }),
        fetch('/api/goals', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...otherGoal,
            order: otherGoal.order - 1,
          }),
        }),
      ])

      setGoals((prev) =>
        prev.map((g) => {
          if (g.id === goalId) return { ...g, order: goal.order + 1 }
          if (g.id === otherGoal.id) return { ...g, order: otherGoal.order - 1 }
          return g
        })
      )
    } catch (error) {
      console.error('Failed to reorder goals:', error)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <p className="text-zinc-400">Loading...</p>
      </div>
    )
  }

  const activeGoals = goals.filter((g) => g.status === 'ACTIVE').sort((a, b) => a.order - b.order)
  const onDeckGoals = goals.filter((g) => g.status === 'ON_DECK').sort((a, b) => a.order - b.order)
  const archivedGoals = goals.filter((g) => g.status === 'ARCHIVED').sort((a, b) => a.order - b.order)

  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-4xl font-bold text-white">Manage Goals</h1>
          <Link
            href="/dashboard"
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-100 text-sm transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>

        <div className="space-y-8">
          {/* Active Goals */}
          <section>
            <h2 className="text-xl font-bold text-white mb-4">Active Goals</h2>
            <div className="space-y-2">
              {activeGoals.map((goal) => (
                <div
                  key={goal.id}
                  className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg p-4"
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-2xl">{goal.emoji}</span>
                    <div>
                      <p className="font-semibold text-white">{goal.title}</p>
                      <p className="text-sm text-zinc-400">{goal.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleMoveUp(goal.id)}
                      className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 text-sm"
                    >
                      ↑
                    </button>
                    <button
                      onClick={() => handleMoveDown(goal.id)}
                      className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 text-sm"
                    >
                      ↓
                    </button>
                    <select
                      value={goal.status}
                      onChange={(e) =>
                        handleStatusChange(goal.id, e.target.value as Goal['status'])
                      }
                      className="px-3 py-1 bg-zinc-800 border border-zinc-700 rounded text-white text-sm"
                    >
                      <option value="ACTIVE">Active</option>
                      <option value="ON_DECK">On Deck</option>
                      <option value="ARCHIVED">Archived</option>
                    </select>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* On Deck Goals */}
          {onDeckGoals.length > 0 && (
            <section>
              <h2 className="text-xl font-bold text-white mb-4">On Deck</h2>
              <div className="space-y-2">
                {onDeckGoals.map((goal) => (
                  <div
                    key={goal.id}
                    className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg p-4 opacity-75"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <span className="text-2xl">{goal.emoji}</span>
                      <div>
                        <p className="font-semibold text-white">{goal.title}</p>
                        <p className="text-sm text-zinc-400">{goal.description}</p>
                      </div>
                    </div>
                    <select
                      value={goal.status}
                      onChange={(e) =>
                        handleStatusChange(goal.id, e.target.value as Goal['status'])
                      }
                      className="px-3 py-1 bg-zinc-800 border border-zinc-700 rounded text-white text-sm"
                    >
                      <option value="ACTIVE">Active</option>
                      <option value="ON_DECK">On Deck</option>
                      <option value="ARCHIVED">Archived</option>
                    </select>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Archived Goals */}
          {archivedGoals.length > 0 && (
            <section>
              <h2 className="text-xl font-bold text-white mb-4">Archived</h2>
              <div className="space-y-2">
                {archivedGoals.map((goal) => (
                  <div
                    key={goal.id}
                    className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-lg p-4 opacity-50"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <span className="text-2xl">{goal.emoji}</span>
                      <div>
                        <p className="font-semibold text-white">{goal.title}</p>
                        <p className="text-sm text-zinc-400">{goal.description}</p>
                      </div>
                    </div>
                    <select
                      value={goal.status}
                      onChange={(e) =>
                        handleStatusChange(goal.id, e.target.value as Goal['status'])
                      }
                      className="px-3 py-1 bg-zinc-800 border border-zinc-700 rounded text-white text-sm"
                    >
                      <option value="ACTIVE">Active</option>
                      <option value="ON_DECK">On Deck</option>
                      <option value="ARCHIVED">Archived</option>
                    </select>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
