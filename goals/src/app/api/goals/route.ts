import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { getSessionToken } from '@/lib/auth'

export async function GET() {
  try {
    const goals = await prisma.goal.findMany({
      where: {
        status: 'ACTIVE',
      },
      orderBy: { order: 'asc' },
      include: {
        habits: {
          orderBy: { order: 'asc' },
          include: {
            logs: {
              orderBy: { date: 'desc' },
              take: 30,
            },
          },
        },
        notes: {
          orderBy: { createdAt: 'desc' },
          take: 3,
        },
      },
    })

    return NextResponse.json(goals, { status: 200 })
  } catch (error) {
    console.error('Get goals error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch goals' },
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
    const { title, description, emoji, status, order, habits } = await request.json()

    const goal = await prisma.goal.create({
      data: {
        title,
        description,
        emoji,
        status: status || 'ACTIVE',
        order: order || 0,
        habits: habits ? {
          create: habits,
        } : undefined,
      },
      include: {
        habits: true,
      },
    })

    return NextResponse.json(goal, { status: 201 })
  } catch (error) {
    console.error('Create goal error:', error)
    return NextResponse.json(
      { error: 'Failed to create goal' },
      { status: 500 }
    )
  }
}

export async function PUT(request: NextRequest) {
  const token = await getSessionToken()
  if (!token) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  try {
    const { id, title, description, emoji, status, order } = await request.json()

    const goal = await prisma.goal.update({
      where: { id },
      data: {
        title,
        description,
        emoji,
        status,
        order,
      },
    })

    return NextResponse.json(goal, { status: 200 })
  } catch (error) {
    console.error('Update goal error:', error)
    return NextResponse.json(
      { error: 'Failed to update goal' },
      { status: 500 }
    )
  }
}

export async function DELETE(request: NextRequest) {
  const token = await getSessionToken()
  if (!token) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  try {
    const { searchParams } = new URL(request.url)
    const id = searchParams.get('id')

    if (!id) {
      return NextResponse.json(
        { error: 'Goal ID is required' },
        { status: 400 }
      )
    }

    await prisma.goal.delete({
      where: { id },
    })

    return NextResponse.json(
      { message: 'Goal deleted' },
      { status: 200 }
    )
  } catch (error) {
    console.error('Delete goal error:', error)
    return NextResponse.json(
      { error: 'Failed to delete goal' },
      { status: 500 }
    )
  }
}
