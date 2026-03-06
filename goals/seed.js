const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function main() {
  // Clear existing data
  await prisma.habitLog.deleteMany({});
  await prisma.note.deleteMany({});
  await prisma.habit.deleteMany({});
  await prisma.goal.deleteMany({});

  // Active Goals
  const goal1 = await prisma.goal.create({
    data: {
      title: 'Master Claude & Engineering',
      description: 'AI tokens logged, daily project work',
      emoji: '🤖',
      status: 'ACTIVE',
      order: 1,
    },
  });

  await prisma.habit.createMany({
    data: [
      {
        goalId: goal1.id,
        name: 'AI Tokens (OpenRouter)',
        order: 1,
      },
      {
        goalId: goal1.id,
        name: 'Project Work',
        order: 2,
      },
    ],
  });

  const goal2 = await prisma.goal.create({
    data: {
      title: 'Health & Habits',
      description: 'Clean meals, sleep hours',
      emoji: '🥗',
      status: 'ACTIVE',
      order: 2,
    },
  });

  await prisma.habit.createMany({
    data: [
      {
        goalId: goal2.id,
        name: 'Clean Meals',
        order: 1,
      },
      {
        goalId: goal2.id,
        name: 'Sleep Hours',
        order: 2,
      },
    ],
  });

  const goal3 = await prisma.goal.create({
    data: {
      title: 'Fitness',
      description: 'Daily workout checkbox, activity',
      emoji: '💪',
      status: 'ACTIVE',
      order: 3,
    },
  });

  await prisma.habit.createMany({
    data: [
      {
        goalId: goal3.id,
        name: 'Workout',
        order: 1,
      },
      {
        goalId: goal3.id,
        name: 'Activity',
        order: 2,
      },
    ],
  });

  const goal4 = await prisma.goal.create({
    data: {
      title: 'Style & Attitude',
      description: 'Outfit intention, journaling',
      emoji: '✨',
      status: 'ACTIVE',
      order: 4,
    },
  });

  await prisma.habit.createMany({
    data: [
      {
        goalId: goal4.id,
        name: 'Outfit Intention',
        order: 1,
      },
      {
        goalId: goal4.id,
        name: 'Journaling',
        order: 2,
      },
    ],
  });

  const goal5 = await prisma.goal.create({
    data: {
      title: 'Read, Write & Build Audience',
      description: 'Pages read, Substack posts, social posts',
      emoji: '📚',
      status: 'ACTIVE',
      order: 5,
    },
  });

  await prisma.habit.createMany({
    data: [
      {
        goalId: goal5.id,
        name: 'Pages Read',
        order: 1,
      },
      {
        goalId: goal5.id,
        name: 'Substack Posts',
        order: 2,
      },
      {
        goalId: goal5.id,
        name: 'Social Posts',
        order: 3,
      },
    ],
  });

  // On Deck Goals
  const goal6 = await prisma.goal.create({
    data: {
      title: 'Martial Arts',
      description: 'Training and progression',
      emoji: '🥋',
      status: 'ON_DECK',
      order: 6,
    },
  });

  await prisma.habit.create({
    data: {
      goalId: goal6.id,
      name: 'Training Sessions',
      order: 1,
    },
  });

  const goal7 = await prisma.goal.create({
    data: {
      title: 'Diving & Australia Reef',
      description: 'Dive certifications and exploration',
      emoji: '🤿',
      status: 'ON_DECK',
      order: 7,
    },
  });

  await prisma.habit.create({
    data: {
      goalId: goal7.id,
      name: 'Dive Practice',
      order: 1,
    },
  });

  const goal8 = await prisma.goal.create({
    data: {
      title: 'Grad School / NZ Citizenship / NS Fellowship',
      description: 'Educational and immigration goals',
      emoji: '🎓',
      status: 'ON_DECK',
      order: 8,
    },
  });

  await prisma.habit.create({
    data: {
      goalId: goal8.id,
      name: 'Applications',
      order: 1,
    },
  });

  const goal9 = await prisma.goal.create({
    data: {
      title: 'Israeli Citizenship',
      description: 'Law of Return application and process',
      emoji: '🇮🇱',
      status: 'ON_DECK',
      order: 9,
    },
  });

  await prisma.habit.create({
    data: {
      goalId: goal9.id,
      name: 'Document Collection',
      order: 1,
    },
  });

  const goal10 = await prisma.goal.create({
    data: {
      title: 'Personal Book Writing',
      description: 'Authoring and publishing',
      emoji: '✍️',
      status: 'ON_DECK',
      order: 10,
    },
  });

  await prisma.habit.create({
    data: {
      goalId: goal10.id,
      name: 'Writing Sessions',
      order: 1,
    },
  });

  console.log('Seed completed successfully!');
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
