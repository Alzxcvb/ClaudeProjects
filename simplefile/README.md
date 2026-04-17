# SimpleFile

Free W-2 tax calculator + filing guide. Built in frustration after TurboTax wasted a full day.

## What it does
1. Upload W-2 photo or PDF
2. AI extracts all box values (via OpenRouter / Gemini Flash — ~$0.001/extraction)
3. Calculates federal 1040 + CA 540 automatically
4. Shows line-by-line breakdown
5. Links to free filing options with your numbers ready

## Stack
Single HTML file. No dependencies, no server, no build step. Everything runs in the browser. Zero PII leaves your device except to the OpenRouter API for W-2 extraction.

## Usage
PDF generation fetches `f1040.pdf` / `ca540.pdf` from the same directory, which requires an HTTP origin (not `file://`). Run a local server:

```
cd simplefile && python3 -m http.server 8000
# open http://localhost:8000
```

Or deploy to GitHub Pages. Enter your OpenRouter API key (saved to localStorage). Upload W-2. Extract. Calculate. Download filled PDFs.

Get a free OpenRouter key at openrouter.ai.

## Filing after calculating
- **Federal:** Download the filled 1040 PDF, verify, sign, and mail (see irs.gov/filing/where-to-file-paper for the address for your state).
- **California (free e-file):** ftb.ca.gov → CalFile → enter CA values from the summary page. Or mail the filled CA 540 PDF.
- Note: IRS Direct File was shut down by DOGE in March 2025. True e-file requires IRS EFIN authorization (months of regulatory approval).

## Scope (current)
- W-2 income only (wages, Box 1)
- Standard deduction (2025: $15,000 single / $30,000 MFJ)
- Pre-tax adjustments: 401(k) Box 12D, HSA Box 12W (already excluded from Box 1)
- Above-the-line: student loan interest deduction (with phase-out)
- California: Form 540, standard deduction, all 9 CA brackets + MHST, SDI credit
- Filing statuses: Single, MFJ, HoH, MFS

## Known limitations / TODO
- No itemized deductions (mortgage interest, charitable, medical — only matters if itemized > standard)
- No investment income (1099-DIV, 1099-B)
- No self-employment income (Schedule C)
- No child tax credit, EITC, or other credits
- No multi-state filing
- True e-file not possible without IRS Authorized e-file Provider status (months of regulatory approval) — filled PDFs for mail filing + CalFile link instead
- AcroForm field names in the filled 1040/540 PDFs are best-effort mappings. Use the "Log PDF field names (debug)" button to verify and refine if any line ends up empty in the output.

## Why we built this
TurboTax has a known 2025 bug: "Person on the Return Worksheet: Enrollmentstatus must be entered" loops infinitely in Smart Check even after completing the CA health coverage interview. The error is a phantom field in the CA worksheet that the federal validator sees as blank but provides no UI to fix. The bug is triggered by: HSA (Form 8889) + CA residency + Expert Assist Deluxe tier. TurboTax funnels you to a paid "Review with a tax expert" upsell instead of fixing it. IRS Direct File was shut down. This is revenge software.

## License
MIT
