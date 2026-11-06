# Indoor-Furniture-Placement-Copilot

## Introduction

Nowadays, as homes become more intelligent and personalized, optimizing space for both aesthetics and functionality is becoming an essential part of modern living. With the assistance of machine learning and co-pilot technologies, it’s possible to get suggestions for ideal furniture layouts based on real-life data such as activity patterns. The indoor furniture placement copilot project utilizes AI and machine learning to create a tool that can give furniture placement plans based on safety and comfort.

## Members

Yongyi Xie xyy0208@bu.edu

## Project Layout

| Path | Contents |
| --- | --- |
| `src/` | React frontend (Welcome, Generation and Result pages) |
| `server/` | Express API (`index.js`), the layout engine and copilot (`layout/`) and their command-line entry point (`placement_generation.py`) |
| `server/tests/` | API tests (`node --test`) and generator tests (`pytest`) |
| `simulation/` | Daily activity path simulation (`path_simulation.py`) and sample output |
| `notebooks/` | Path and layout visualization notebook |
| `docs/` | Course deliverables (project plan, slides, poster, reports) |

## Getting Started

Requirements: Node.js 18+ and Python 3.9+.

### 1. Backend (port 5000)

```bash
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
npm install
npm start
```

The server runs the layout engine with `server/.venv`'s Python when it exists; otherwise set `PYTHON` to the interpreter to use.

To turn on the Claude copilot, give the server Claude API credentials before `npm start`, e.g.
`export ANTHROPIC_API_KEY=...` (or sign in with `ant auth login`). Without credentials the app still works; see
[The copilot](#the-copilot).

### 2. Frontend (port 3000)

```bash
npm install
npm start
```

Open http://localhost:3000. To point the frontend at a different API, set `REACT_APP_API_URL` (default `http://localhost:5000`);
to accept a different frontend origin on the server, set `CLIENT_ORIGIN` (default `http://localhost:3000`).

### API

`GET /api/options` returns the furniture types and default sizes, the presets, input limits and form defaults.

`POST /api/generate` takes a layout request (lengths in feet):

```json
{
  "preset": "child_safe",
  "room": {
    "width": 16, "length": 14,
    "doors": [{"wall": "bottom", "offset": 1, "width": 3}],
    "windows": [{"wall": "top", "offset": 5, "width": 5}]
  },
  "furniture": [{"type": "bed", "count": 1, "width": 5, "depth": 6.5}, {"type": "desk", "count": 1}],
  "notes": "toddler at home",
  "preferences": [{"kind": "near", "piece": "bed", "target": "window", "strength": "high"}],
  "seed": 42
}
```

- `wall` is `bottom`, `right`, `top` or `left`; `offset` runs from the wall's left (bottom/top) or bottom (left/right) end.
- Furniture `width` runs along the front and `depth` front to back; both default to the type's usual size.
- `preset` may also be `"auto"`: the copilot picks one from the notes.
- `preferences` is optional. Leave it out to have the copilot derive preferences from `notes`; send a list (even
  an empty one) to use exactly those. Each has `kind` (`near`, `away`, `against_wall`), `piece` (a furniture type),
  `target` (`window`, `door`, `center`, `wall:bottom|right|top|left` or a furniture type) and `strength`
  (`low`, `medium`, `high`).
- `seed` is optional; the same request and seed always give the same layout.

Responses:

- `200` with the layout: `room`, `furniture` (centre `x`/`y`, `rotation` = direction the front faces, 0 = up, 90 = right, …),
  `metrics` (largest open area, walkway width, unreachable or cramped pieces, cost breakdown), `warnings`,
  `preferences` (each with `met`), `flow` (daily foot traffic), `copilot` (`online`, `reply`, `explanation`,
  `notices`) and `request`: the request with the preset, preferences and seed resolved, to send back to regenerate
  or refine without asking the copilot again
- `400 {"error": "..."}` for invalid input or furniture that does not fit
- `500 {"error": "..."}` if the engine fails

`POST /api/refine` changes a layout as a chat message asks:
`{"request": <layout.request>, "layout": {"furniture": [{"id", "x", "y", "rotation"}, ...]}, "message": "put the desk by the window", "history": [{"role": "user", "text": "..."}, {"role": "assistant", "text": "..."}]}`.
The copilot updates the preset and preferences, and the engine starts from the current layout and pays for every
piece it moves, so only what the message is about changes. It returns a layout like `/api/generate`.

## The copilot

`server/layout/copilot.py` uses Claude (`claude-opus-5-5`, low effort, with server-side refusal fallbacks) to:

- read the notes, and later chat messages, into a preset and placement preferences, using structured output whose
  schema only allows the engine's furniture types, targets and presets;
- explain each finished layout in 3–5 sentences, in the language the user wrote in.

If no credentials are configured, the API cannot be reached, or `COPILOT_OFFLINE=1` is set, the copilot falls back:
it picks a preset from keywords in the notes (English and Chinese), explains the layout from a template, and the
result page says the copilot is offline. Tests always run offline.

## Daily foot traffic

After a layout is chosen, `server/layout/flow.py` simulates a day for each occupant (one per bed):
bed → wardrobe → door → desk → sofa → wardrobe → bed, each trip along the shortest walkway. The result page shows
the walking distance per person and, on request, a heatmap of where people walk.

## How layouts are generated

The engine in `server/layout/` searches for a layout with simulated annealing (4 restarts × 1200 steps), scoring each candidate:

| Kind | Rule |
| --- | --- |
| Hard | No overlaps, everything inside the room, nothing in a door's swing. A request that cannot meet these is rejected. |
| Walkways | A person (or wheelchair) must fit between furniture and walls on the way from a door to the front of every piece. |
| Clearance | Free floor in front of each piece (e.g. 3 ft for a desk). |
| Placement | Beds, desks, TV stands and wardrobes back onto a wall; tall furniture stays clear of windows; the TV faces the sofa or bed. |
| Open space | The largest open circle of floor, away from furniture, walls and door swings. |

Presets reweight these rules for the user stories:

| Preset | What changes |
| --- | --- |
| Balanced | Defaults: 30 in walkways. |
| Child-safe | Large open play area (at least 6 ft across); fragile, sharp and tall pieces against walls and away from it. |
| Wheelchair accessible | 36 in walkways and 5 ft turning space in front of every piece. |
| Shared studio | Beds spread apart for privacy, desks grouped for group work, more open space. |

When the room is too tight for a preset's rules the layout is still returned, with warnings saying what falls short.

### Tests

```bash
npm test -- --watchAll=false          # frontend
cd server && npm test                 # API
cd server && .venv/Scripts/python -m pytest tests   # layout engine
```

## User Stories
### User Story 1: Child-Safe Room Design for Parents
	A mother wants to make her living room safe for her toddler, ensuring that sharp or fragile furniture is kept out of the child’s reach. She seeks help from the furniture placement copilot to suggest an arrangement that leaves ample space for her child to play without tripping hazards.
### User Story 2: Accessible Bedroom for Mobility-Impaired Adults
	A wheelchair user needs a bedroom layout that provides easy access to the bed, closet, and desk, with enough space to maneuver the wheelchair. The copilot assists in rearranging furniture to optimize accessibility while maintaining functionality.
### User Story 3: Shared Space Optimization for Tenants
	A group of four students, two boys, and two girls, live in one studio, with boys needing space to play together, girls gossiping together, and everyone getting privacies. They also need some space for group work. They want the furniture arranged to accommodate everyone’s needs without making the space feel cramped or chaotic.
## History
10/14: Data Generation completed in main.py. The sample output is in path.json, in the format of [start_time_since_00:00_in_seconds, x_position_in_feet, y_position_in_feet]. The original point starts from the bottom-left corner of the room, which is a rectangle.
In main.py, furniture and people classes are defined. Details are included in the file.

11/7: Path and room Layout Visualizations. Given input furniture numbers, the program can output a basic design, ensuring they don't collide.

Express.js creation. This involves creating the backend part. Using node.js, I implemented a call for OpenAI API and made a local server.

11/25: Javascript + CSS implementation of front-end design. Established the structure of three pages, WelcomePage, Generation Page and Result Page.
I use React package to implement the frame. All codes in master branch.

12/5: Connect frontend (on localhost:3000) to backend (on localhost:5000/api/generate), and go through unit testing.

## Roadmap

- Drag furniture to adjust a layout, compare several layouts side by side, export to PNG or JSON.

## References
[1] L. Yanhua, “Optimizing Space with AI: Intelligent Design Solutions for Soft Furnishings and Decor,” International Journal of Science and Engineering Applications, vol. 13, no. 7, Jun. 2024, doi: https://doi.org/10.7753/ijsea1307.1008

[2] S. I. Mohamed, M. M. Saady, and Z. A. E. H. Taha, “Virtual Utopia: AI-Enhanced 3D Room Design Simulation for Optimal Furniture Layout,” 2024 Intelligent Methods, Systems, and Applications (IMSA), pp. 489–494, Jul. 2024, doi: https://doi.org/10.1109/imsa61967.2024.10652795

[3] A. Penn and A. Turner, “Space layout affects search efficiency for agents with vision,” 2003. Available: https://www.spacesyntax.net/symposia-archive/SSS4/fullpapers/09Penn-Turner.pdf. [Accessed: Oct. 01, 2024]

[4] K. G., “Layout design for efficiency improvement and cost reduction,” Bulletin of the Polish Academy of Sciences: Technical Sciences, 2019, doi: https://doi.org/10.24425/bpasts.2019.129653. Available: https://journals.pan.pl/dlibra/publication/129653/edition/113167/content

[5] M. Ran and J. Dong, “A Multiobjective Optimization Algorithm for Building Interior Design and Spatial Structure Optimization,” Mobile Information Systems, 	vol. 2022, pp. 1–15, Jul. 2022, doi: https://doi.org/10.1155/2022/5659280

[6] L. Chen, C. Nugent, and G. Okeyo, “An Ontology-Based Hybrid Approach to Activity Modeling for Smart Homes,” IEEE Transactions on Human-Machine Systems, vol. 44, no. 1, pp. 92–105, Feb. 2014, doi: 	https://doi.org/10.1109/thms.2013.2293714
