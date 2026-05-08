export interface HabitLog {
  id: string
  habitId: string
  completed: boolean
  value?: number
  date?: string
}

export interface Habit {
  id: string
  name: string
  order: number
  goalId?: string
  logs?: HabitLog[]
}

export interface Note {
  id: string
  content: string
  milestone: boolean
  date: string
}

export interface Goal {
  id: string
  title: string
  emoji: string
  habits: Habit[]
  description?: string
  notes?: Note[]
}
