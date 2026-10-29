# Case study (D10): draft outline

**Status: outline only.** The brief asks for a 1,500–2,500-word case study with screenshots, the build story, the builder's project-management artifacts beside the app's generated artifacts, simulation findings, and lessons / change proposals. Fill it with measured results only. Do not invent adoption, completion or user-test figures.

## Sections to write

1. **Problem and users** (from discovery interviews, which have not yet been held; see `project-plan/gate-reviews.md`)
2. **Approach compared**: Eventbrite organizer tools, generic PM templates, spreadsheet templates (comparison still to be done)
3. **Build story**: gates, what slipped, decisions (link `decisions.md`)
4. **Side by side**: builder's WBS / Gantt / risk register (`project-plan/`) next to WellnessPop's generated ones for a demo
5. **Simulation findings**: e.g. what the three demos show (fill in from the deployed app, with seed and run count)
6. **User testing**: two unaided sessions, times and top five issues fixed (not yet done)
7. **Lessons and change proposals**

## Facts already measurable (29 October 2026, local machine, Python 3.12.10)

- 85 automated tests pass (calculations, imports, exports, privacy, UI).
- 10,000-run simulations complete in about 0.01–0.04 seconds per demo on the development machine (deployed timing not yet measured).
- Demo results at seed 42 (illustrative assumptions): A 8% chance of breaking even; B 15%; C 2% (C targets a −$500 subsidized result).
