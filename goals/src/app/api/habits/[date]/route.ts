import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { getSessionToken } from '@/lib/auth'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params

    const logs = await prisma.habitLog.findMany({
      where: {
        date,
      },
      include: {
        habit: {
          include: {
            goal: true,
          },
        },
      },
      orderBy: {
        habit: {
          order: 'asc',
        },
      },
    })

    return NextResponse.json(logs, { status: 200 })
  } catch (error) {
    console.error('Get habit logs error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch habit logs' },
      { status: 500 }
    )
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  const token = await getSessionToken()
  if (!token) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  try {
    const { date } = await params
    const { habitId, completed, value } = await request.json()

    const log = await prisma.habitLog.upsert({
      where: {
        habitId_date: {
          habitId,
          date,
        },
      },
      update: {
        completed,
        value,
      },
      create: {
        habitId,
        date,
        completed,
        value,
      },
      include: {
        habit: {
          include: {
            goal: true,
          },
        },
      },
    })

    return NextResponse.json(log, { status: 200 })
  } catch (error) {
    console.error('Upsert habit log error:', error)
    return NextResponse.json(
      { error: 'Failed to save habit log' },
      { status: 500 }
    )
  }
}
