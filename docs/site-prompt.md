Paste this into Cursor/Codex.

You are a product engineer, frontend architect, and design-heavy data-visualization specialist.

Build a recruiter-impressive portfolio micro-site from my Chess.com PGN export using Next.js + TypeScript. The goal is to make software engineering recruiters — especially frontend recruiters — immediately think: “this person can build polished, data-rich, interactive products with taste.”

## Primary objective

Turn a raw Chess.com PGN export into a premium, animated, interactive analytics site centered on **Elo over time**, with enough engineering quality and visual polish that it doubles as a frontend portfolio piece.

This should feel like:

* premium product design
* thoughtful data storytelling
* excellent motion and interaction design
* strong TypeScript / architecture hygiene
* production-ready engineering, not a hackathon blob creature

## Input data

Use this PGN file as the source of truth:

* preferred repo path: `./games/all/chess_com_games_2026-03-15_combined.pgn`
* if the file only exists at `/mnt/data/chess_com_games_2026-03-15_combined.pgn`, copy it into the repo under `./games/all`

Assume the PGN is a Chess.com export containing standard tags like:

* Date
* White / Black
* WhiteElo / BlackElo
* Result
* TimeControl
* Termination
* moves

Infer the player identity from the PGN automatically if possible. If needed, derive it from the most common repeated username.

## Tech requirements

Use:

* Next.js latest stable with App Router
* TypeScript strict mode
* Tailwind CSS
* shadcn/ui
* Motion for animation
* Recharts for charts
* chess.js for PGN / move logic
* react-chessboard for board rendering
* lucide-react for icons
* date-fns for date handling
* zod for data validation / parsing where helpful
* next/font for typography
* dynamic metadata / OG image support

You may add any other libraries that materially improve the result, but keep the stack coherent and defensible.

## Design direction

Make it **as fancy as possible**, but in a tasteful way:

* dark, premium, recruiter-friendly aesthetic by default
* subtle gradients, glows, glass, noise, grid texture, depth
* not cheesy gamer neon sludge
* elegant motion everywhere, but never annoying
* respect `prefers-reduced-motion`
* make charts and cards feel alive
* use layout transitions, staggered entrances, hover states, shared element transitions where appropriate
* the site should feel expensive

Design inspiration vibe:

* Vercel / Linear / modern analytics dashboard
* editorial storytelling + interactive dashboard
* chess elegance, not chess kitsch

## Product framing

This is not “here are my chess games.”
This is:

* a polished analytics product
* a personal data story
* a demonstration of frontend engineering, information design, and interaction design

The copy should frame the project for recruiters:

* turning raw PGN exports into typed, interactive analytics
* build-time / server-side data processing
* accessible component architecture
* production-minded UX
* strong motion + data-viz craft

## Information architecture

Create a multi-section experience with a strong landing page and supporting views.

### Routes

At minimum:

* `/` → premium landing page / overview
* `/games` → searchable, filterable game explorer
* `/games/[id]` or modal/detail route → full game detail + replay
* `/insights` → deeper stats / trends / breakdowns

Optional:

* `/about` or a “How this was built” section on home

## Core features

### 1) Hero section

Create a genuinely impressive landing hero with:

* project title
* one-line recruiter-facing positioning
* animated Elo sparkline / mini chart
* key stats card cluster
* highlighted current / peak rating
* short “why this project exists” copy
* CTA buttons into Insights and Games
* subtle background motion/parallax
* a floating or embedded chessboard visual for extra texture

This should be the “damn, okay” moment.

### 2) Elo over time visualization

This is the centerpiece.

Build a beautiful, interactive Elo-over-time chart with:

* line chart of rating by game date / sequence
* optional rolling average
* optional point markers for wins / losses / draws
* gradient fill / polished tooltip / crosshair
* filters:

  * all / white / black
  * result
  * time control
  * date range
* chart interactions:

  * hover tooltips with game metadata
  * click a point to open game details
  * zoom / brush / range selection if useful
* visually highlight:

  * peak rating
  * worst dip
  * longest streak
  * biggest rating jumps
* add annotations / callouts for meaningful milestones

Make the chart gorgeous and recruiter-grade.

### 3) Stats and insight cards

Compute and visualize:

* current rating
* peak rating
* lowest rating
* rating change over selected period
* win / loss / draw counts
* win rate
* white vs black performance
* most common time control
* longest win streak
* longest loss streak
* average game length in plies / moves
* most common termination types
* most active day / week
* best recent form
* volatility / consistency indicators

Present these as polished cards with micro-interactions and mini visualizations where appropriate.

### 4) Game explorer

Build a premium game browser:

* searchable
* sortable
* filterable
* pagination or virtualized rendering if needed
* columns such as:

  * date
  * color
  * opponent
  * result
  * rating
  * rating delta
  * time control
  * termination
  * move count
* responsive design
* details drawer or route on click

Make the table feel serious and well-designed, not default-library mush.

### 5) Game detail / replay experience

For each game:

* render a chessboard
* replay moves forward/backward
* move list with current move highlighting
* autoplay controls
* jump to start / end
* move slider or scrubber
* show metadata and tags
* show final result / termination
* surface interesting moments if derivable
* display FEN progression derived from the move history
* compute and display material balance over time if feasible

This should feel like a polished analysis viewer even without engine integration.

### 6) Openings / patterns section

If practical, derive lightweight opening insights:

* common first moves
* common opening families
* most frequent move prefixes
* white and black opening tendencies

If exact ECO naming becomes annoying, implement a graceful fallback:

* infer opening “signatures” from early SAN move sequences
* label clearly when heuristic

Do not stall the project over perfect opening taxonomy.

### 7) “How it was built” / recruiter section

Include a section that explicitly sells the engineering:

* PGN parsing pipeline
* typed data model
* derived analytics
* charting architecture
* accessibility considerations
* motion system
* App Router structure
* performance decisions
* metadata / OG generation
* why this demonstrates frontend engineering skill

This is the recruiter bait, but make it classy.

## Data pipeline requirements

Create a clean, typed parsing + transformation pipeline.

### Parse and normalize

From the PGN, derive a normalized game model with fields such as:

* id
* date
* sequence number
* player color
* opponent name
* result
* player rating
* opponent rating
* rating delta if derivable
* time control
* termination
* SAN moves
* ply count
* move count
* start/end metadata
* raw headers

### Derived analytics

Compute:

* Elo series by date and by game index
* moving average(s)
* streaks
* result breakdowns
* white/black splits
* time-control splits
* activity heatmap data
* rolling form
* volatility measures
* termination breakdown
* top opening signatures
* recent trend summaries

### Implementation style

* keep pure transformation functions where possible
* keep parsing logic separate from UI
* validate risky inputs
* handle malformed PGN gracefully
* add defensive error states
* generate a derived JSON cache if that improves performance / simplicity

### Scripts

Add npm scripts for:

* ingest / parse PGN
* rebuild derived data
* dev
* build
* lint
* typecheck

## Engineering requirements

### Code quality

* strict TypeScript
* no `any` unless absolutely unavoidable and justified
* clean component boundaries
* reusable hooks/utilities
* clear folder structure
* robust types for domain models
* avoid spaghetti state

### Comments

Use detailed, self-documenting comments for non-obvious logic.
Do not comment trivial lines.
Focus comments on:

* parsing assumptions
* analytics derivations
* tricky UI state
* why a design/architecture decision exists

### README

Update the README so it clearly covers:

* what the project is
* why it exists
* stack
* data source
* how PGN ingestion works
* how to run locally
* how to rebuild derived data
* how to deploy
* architecture overview
* future enhancements

### Testing

Add lightweight but real tests for the most important logic:

* PGN parsing / normalization
* rating series derivation
* streak calculations
* any heuristics used for opening signatures

Do not overbuild the test suite, but include enough to show seriousness.

## UX requirements

### Accessibility

* keyboard-friendly interactions
* good focus states
* semantic markup
* color contrast that is actually usable
* motion-safe fallbacks
* chart tooltips and controls that are not inaccessible goblins

### Performance

* avoid unnecessary client-side work
* server components where sensible
* client components only where interactivity needs them
* avoid absurd bundle bloat
* lazy-load heavy views if helpful

### Responsiveness

* excellent desktop presentation
* still strong on mobile
* charts should degrade gracefully on small screens
* tables should remain usable

## Visual polish requirements

Include premium details like:

* animated page transitions
* staggered entrances
* card hover effects
* chart glow / gradient polish
* subtle background grid/noise
* shared layout transitions
* elegant skeleton loaders
* empty states and error states that still look designed

But:

* no clutter
* no gratuitous fireworks
* no fake complexity
* no “dashboard because dashboard” nonsense

## SEO / shareability

Implement:

* polished metadata
* dynamic or static OG image
* strong page titles / descriptions
* favicon / app icon
* shareable preview that looks deliberate

## Deliverables

I want you to fully implement the project, not just sketch it.

At the end, return:

1. a concise architecture summary
2. the file tree
3. the key implementation notes
4. any assumptions made
5. run commands
6. any future enhancements worth doing later

## Suggested folder structure

Use a clean App Router structure such as:

* `app/`
* `components/`
* `lib/`
* `data/`
* `public/`
* `types/`
* `scripts/`
* `tests/`

Organize by clarity, not dogma.

## Extra credit features

If they fit naturally, add:

* streak timeline
* activity heatmap calendar
* matchup filters by opponent
* “best win / toughest loss” spotlight cards
* mini insights generated from the data
* animated hero chart that responds to cursor
* beautiful command palette or filter sheet
* downloadable CSV / JSON derived from PGN
* screenshot-friendly “stats summary” card
* route-level OG images

## Tone of the final product

Confident, polished, thoughtful, modern.
A serious frontend portfolio project disguised as chess analytics.

Build something that makes a recruiter think:
“This person can take ugly raw data and turn it into a product.”

That prompt is already aimed at a coding agent that likes to wander off into the swamp, so it pins both the polish and the engineering story.
