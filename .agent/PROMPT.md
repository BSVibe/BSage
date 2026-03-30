You are a developer working on this project.

Read .agent/tasks.json and select the highest-priority task where passes is false.
Implement it according to the description and acceptanceCriteria.

After implementation:
1. Verify: run the acceptance criteria commands
2. If verification passes: git commit with descriptive message (no Co-Authored-By)
3. Update .agent/tasks.json: set passes to true for the completed task
4. Append findings to .agent/progress.txt

For REVIEW tasks:
- Run git diff main and review ALL changes
- Fix all issues found. Only mark passes:true when ZERO issues remain

IMPORTANT: Only work on ONE task per invocation. Do not skip ahead.

## Playwright E2E Guidelines
- Use page.route() to mock ALL API responses — tests must work without a running backend
- Test that pages render correctly: key elements visible, correct text content
- Test navigation between pages
- Test interactions: button clicks, modal open/close, form inputs
- Use expect(locator).toBeVisible() for assertions
- Install Playwright browsers if needed: npx playwright install chromium && npx playwright install-deps chromium
- playwright.config.ts should use baseURL: http://localhost:PORT (check vite config for the port)
- Start the frontend dev server before tests if not already running

## BSVibe Design System Check
- Body: bg gray-950 (#0a0b0f)
- Cards: bg gray-900 (#111218)
- Text: gray-50 primary, gray-400 secondary
- Borders: gray-700 (#2a2d42)
- Font: Plus Jakarta Sans, JetBrains Mono for code
- Accent via CSS variable --color-accent
- No white backgrounds, no light mode, no Tailwind default colors
