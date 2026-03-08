import puppeteer from 'puppeteer';
import path from 'path';

export interface ScoreResult {
  score: number;
  details?: string;
  error?: string;
}

export async function scorePhoto(photoPath: string): Promise<ScoreResult> {
  const absolutePath = path.resolve(photoPath);
  let browser;

  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    // Set a realistic user agent
    await page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    );

    await page.goto('https://www.attractivenesstest.com', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });

    // Upload the photo via the file input
    const fileInput = await page.$('input#imageFile');
    if (!fileInput) {
      throw new Error('Could not find file input #imageFile');
    }
    await (fileInput as any).uploadFile(absolutePath);

    // Wait for preview to load
    await page.waitForFunction(
      () => {
        const preview = document.getElementById('preview') as HTMLImageElement;
        return preview && preview.src && !preview.src.includes('placeholder');
      },
      { timeout: 10000 }
    ).catch(() => {
      // Preview may not change — continue anyway
    });

    // Small delay to let UI update
    await new Promise(r => setTimeout(r, 1000));

    // Click the analyze button
    const submitBtn = await page.$('[onclick*="submitform2"]');
    if (!submitBtn) {
      // Try alternative selectors
      const buttons = await page.$$('button');
      let clicked = false;
      for (const btn of buttons) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.toLowerCase().includes('analy')) {
          await btn.click();
          clicked = true;
          break;
        }
      }
      if (!clicked) {
        throw new Error('Could not find submit button');
      }
    } else {
      await submitBtn.click();
    }

    // Wait for navigation or result to appear (the form submits to a new page)
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {
      // May not navigate — result could appear on same page
    });

    // Wait for results to render
    await new Promise(r => setTimeout(r, 3000));

    // Try to extract the score from the results page
    const result = await page.evaluate(() => {
      const body = document.body.innerText;

      // Look for score patterns like "7.5/10", "Score: 7.5", etc.
      const patterns = [
        /(\d+\.?\d*)\s*\/\s*10/,
        /score[:\s]+(\d+\.?\d*)/i,
        /rating[:\s]+(\d+\.?\d*)/i,
        /attractiveness[:\s]+(\d+\.?\d*)/i,
      ];

      for (const pattern of patterns) {
        const match = body.match(pattern);
        if (match) {
          return { score: parseFloat(match[1]), text: body.substring(0, 500) };
        }
      }

      // Try to find any prominent number that could be the score
      const headings = document.querySelectorAll('h1, h2, h3, .score, .result, .rating');
      for (const el of headings) {
        const text = el.textContent || '';
        const numMatch = text.match(/(\d+\.?\d*)/);
        if (numMatch) {
          const num = parseFloat(numMatch[1]);
          if (num >= 1 && num <= 10) {
            return { score: num, text: body.substring(0, 500) };
          }
        }
      }

      return { score: -1, text: body.substring(0, 1000) };
    });

    if (result.score < 0) {
      return {
        score: 0,
        error: 'Could not extract score from results page',
        details: result.text,
      };
    }

    return { score: result.score, details: result.text };
  } catch (err: any) {
    return {
      score: 0,
      error: `Scoring failed: ${err.message}`,
    };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}
