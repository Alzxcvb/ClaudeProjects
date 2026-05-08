import { PrismaClient } from '@prisma/client'

const globalForPrisma = global as unknown as { prisma: PrismaClient }

/**
 * Shared Prisma client singleton. Reuses one instance across hot reloads in
 * development and per-request invocations in production to avoid exhausting
 * the database connection pool.
 */
export const prisma =
  globalForPrisma.prisma ||
  new PrismaClient({
    log: ['warn', 'error'],
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
