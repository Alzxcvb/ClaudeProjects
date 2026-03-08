import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'https://openrouter.ai/api/v1',
  apiKey: process.env.OPENROUTER_API_KEY || '',
});

const MODEL = process.env.AI_MODEL || 'google/gemini-2.0-flash-001';

interface AnalysisInput {
  scores: Array<{ photoFile: string; score: number }>;
  averageScore: number;
  percentile: number;
  profile: {
    age?: number;
    gender?: string;
    location?: string;
    height?: string;
    bodyType?: string;
    lookingForAgeMin?: number;
    lookingForAgeMax?: number;
    lookingForGender?: string;
    interests?: string;
    bio?: string;
  };
}

export async function generateSuggestions(input: AnalysisInput): Promise<string> {
  const prompt = `You are a dating profile optimization expert. Be direct, specific, and actionable.

USER PROFILE:
- Age: ${input.profile.age || 'Unknown'}
- Gender: ${input.profile.gender || 'Unknown'}
- Location: ${input.profile.location || 'Unknown'}
- Height: ${input.profile.height || 'Unknown'}
- Body Type: ${input.profile.bodyType || 'Unknown'}
- Interests: ${input.profile.interests || 'None listed'}
- Current Bio: ${input.profile.bio || 'None provided'}

ATTRACTIVENESS SCORES:
- Individual photo scores: ${input.scores.map(s => s.score).join(', ')}
- Average score: ${input.averageScore}/10
- Percentile ranking: Top ${100 - input.percentile}% (${input.percentile}th percentile)

LOOKING FOR:
- Gender preference: ${input.profile.lookingForGender || 'Not specified'}
- Age range: ${input.profile.lookingForAgeMin || '?'}-${input.profile.lookingForAgeMax || '?'}

Based on this data, provide a detailed analysis with these sections:

## Photo Analysis & Tips
Analyze score variation between photos. Give specific advice on lighting, angles, expressions, outfit choices, backgrounds, and photo variety. Be honest about what's working and what isn't.

## Bio Optimization
${input.profile.bio ? 'Review their current bio and suggest specific improvements.' : 'Suggest a strong bio based on their profile.'}

## Profile Strategy
Based on their score and demographics, what dating apps/strategies would work best? Be realistic about expectations given their percentile ranking.

## Quick Wins
List 3-5 specific, actionable things they can do THIS WEEK to improve their dating profile.

Be honest but constructive. No sugar-coating, but be respectful.`;

  const response = await client.chat.completions.create({
    model: MODEL,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 2000,
  });

  return response.choices[0]?.message?.content || 'Analysis could not be generated.';
}

export async function generateTypeInsights(input: AnalysisInput): Promise<string> {
  const prompt = `You are a dating market analyst. Based on this person's preferences, give them insights about what their target demographic typically values in dating profiles.

This person is:
- ${input.profile.age || '?'} year old ${input.profile.gender || 'person'}
- Located in ${input.profile.location || 'unknown location'}
- Attractiveness: ${input.averageScore}/10 (${input.percentile}th percentile)

They're looking for:
- ${input.profile.lookingForGender || 'Partners'} aged ${input.profile.lookingForAgeMin || '?'}-${input.profile.lookingForAgeMax || '?'}

Provide insights in these sections:

## What ${input.profile.lookingForGender || 'Your Target Demographic'} (${input.profile.lookingForAgeMin}-${input.profile.lookingForAgeMax}) Typically Value
Top 5 things this demographic looks for in dating profiles, ranked by importance.

## Your Competitive Advantages
Based on their profile, what strengths can they leverage?

## Realistic Expectations
Given their percentile (${input.percentile}th), what tier of matches should they realistically target? Be honest but not cruel.

## Strategic Recommendations
How should they position themselves to maximize matches with their preferred demographic?

Be data-informed and direct. Reference real dating market dynamics.`;

  const response = await client.chat.completions.create({
    model: MODEL,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 1500,
  });

  return response.choices[0]?.message?.content || 'Insights could not be generated.';
}
