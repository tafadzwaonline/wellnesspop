# User guide

WellnessPop helps you plan one community wellness class or one-day fair and see whether it is likely to cover its costs. It takes about 15 minutes to fill in a plan from scratch, or seconds to start from a demo.

## 1. Start

- **Navigation:** the sidebar groups pages into Overview, Plan, Finances, Project and Share. On a phone, open it with the arrow at the top left.
- **Blank plan:** the app opens on the Dashboard with a welcome panel and sensible defaults you can change (**Enter my event**).
- **Demo:** pick *A: Saturday Yoga in the Park*, *B: Evening Sound Bath* or *C: One-Day Wellness Fair* on the welcome panel or in the sidebar and click **Load demo**. This replaces your current plan.
- **Clear plan:** in the sidebar open **Reset plan**, tick *I want to clear this plan*, then click **Clear plan**. Your inputs, results, uploads and downloads are removed from this session.
- **Light or dark theme:** ⋮ menu (top right) › Settings.

Your plan is kept only while this browser session is open. Download the Excel workbook to keep a copy.

## 2. Enter your assumptions (Inputs page)

Each tab has its own **Apply** button. The whole plan is checked first; if anything is invalid you see which field to fix and nothing changes.

| Tab | What to enter |
|---|---|
| Event & goals | Name, type, indoor/outdoor/hybrid, date and times, goal, target attendance and net income, optional spending limit |
| Venue | Capacity, rental and deposit, permit and insurance costs and lead times, and how much of each you would still pay if the event is cancelled |
| Costs | Fixed costs (tick *Uncertain* to give a low / most likely / high range) and per-attendee costs |
| Pricing & attendance | Low / likely / high **registrations** (sign-ups before no-shows), no-show rates, processing fee, ticket tiers and other revenue |
| Staffing | Roles (not names), counts, pay, volunteers, credentials and coverage ratios |
| Marketing | Earliest start, channels and budget |
| Risk assumptions | Weather cancellation probability, rain plan, simulation seed and runs |
| Import | Download a template, upload a CSV or XLSX, preview it, then apply |

Rates are typed as percentages (20 means 20%). Ticket tier shares for weighted tiers must add up to 100%. Fixed free places are filled first.

## 3. Read the outputs

- **Dashboard:** seven key measures on one screen. Each shows a status word as well as an icon.
- **Budget:** net income at low, likely and high registrations, plus the fixed-cost ledger and cash needed up front.
- **Break-even:** how many registrations (and people on site) you need, and the average ticket price that breaks even at likely registrations.
- **Simulation:** click **Run simulation**. Open *How to read this* for a plain-language explanation. If you change inputs, results are marked out of date until you run it again.
- **WBS and Gantt:** tasks are generated from your inputs. Edit them in the WBS table and click **Apply task changes**; your edits survive date changes. Overdue tasks and date conflicts are flagged, not silently moved.
- **Risks:** edit likelihood, impact, owner role, response and status. Scores do not change the simulation; edit the linked assumption instead.
- **Staffing:** costs, recommended counts and missing credentials.
- **Marketing:** a dated checklist per channel. Marking an item complete does not send anything. Download it as CSV.
- **Exports:** Excel workbook (8 sheets), one-page PDF, marketing CSV. If the simulation has not been run, the PDF says it is incomplete.

## 4. Import formats

- XLSX template sheets: Event, Attendance (field / value rows), Costs, Pricing, Staffing, Marketing, Revenue (one row per record). A README sheet is ignored.
- CSV: one table at a time (Costs, Pricing, Staffing, Marketing or Revenue). Choose which table it replaces.
- Dates `YYYY-MM-DD`, money as plain numbers, rates as fractions (0.2 = 20%).
- Limits: 5 MB, 5,000 rows per table. Formulas, macros and external links are rejected.

## 5. Desktop, tablet and phone

WellnessPop is one responsive web app; nothing needs installing on the device you use it from.

- **Desktop / laptop:** any current browser (Chrome, Edge, Firefox, Safari). On Windows you can double-click **Start WellnessPop.cmd** in the project folder: it sets itself up the first time, starts the app and opens your browser.
- **Tablet:** headline numbers wrap into rows; open or close the sidebar with the arrow at the top left.
- **Phone:** pages stack into one column, headline numbers show two per row, the Timeline page becomes a dated agenda (the chart returns on wider screens), input tabs wrap so every tab is visible, and every page ends with **Previous / Next** links so you rarely need the sidebar. Wide editable tables scroll sideways with the task, risk or activity name pinned on the left.
- **Opening it on your phone:** once the app is hosted (see `deployment.md`), open its `streamlit.app` address. While it runs on your own computer, a phone on the **same Wi-Fi** can open `http://<your computer's local IP>:8501` (Windows may ask you to allow Python through the firewall). Anyone on that network can reach it while it runs, so only do this on a network you trust.
- **Home-screen shortcut:** in your phone browser use *Add to Home Screen* (Safari: Share menu; Chrome: ⋮ menu). It opens like an app but still runs in the browser. There is no app-store app: native mobile apps are outside the project scope.

## 6. Accessibility

All controls are keyboard-operable Streamlit widgets with visible labels. Every chart has a table alternative, and statuses use words and icons, not color alone. On a phone, open the sidebar with the arrow at the top left.
