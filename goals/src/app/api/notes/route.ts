import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { getSessionToken } from '@/lib/auth'

export async function GET(request: NextRequest) {
  try {
    const notes = await prisma.note.findMany({
      orderBy: { date: 'desc' },
      include: {
        goal: true,
      },
      take: 50,
    })

    return NextResponse.json(notes, { status: 200 })
  } catch (error) {
    console.error('Get notes error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch notes' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  const token = await getSessionToken()
  if (!token) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  try {
    const { goalId, content, milestone, date } = await request.json()

    const note = await prisma.note.create({
      data: {
        goalId,
        content,
        milestone: milestone || false,
        date: date || new Date().toISOString().split('T')[0],
      },
      include: {
        goal: true,
      },
    })

    return NextResponse.json(note, { status: 201 })
  } catch (error) {
    console.error('Create note error:', error)
    return NextResponse.json(
      { error: 'Failed to create note' },
      { status: 500 }
    )
  }
}
