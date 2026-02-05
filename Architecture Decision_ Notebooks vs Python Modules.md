# Architecture Decision: Notebooks vs Python Modules
## The Question
Should we:
1. Mirror the 5-phase notebook structure in Python modules (parallel structure)
2. Create a different, production-optimized module structure (decoupled structure)
3. Do both (notebooks for demos, modules for production)
## Current State
We have:
* Phase 0-4 notebooks (for demonstration/exploration)
* `profile_extraction.py` module (core functions)
* Optimization A implemented in module signature
## Option 1: Parallel Structure (Notebooks = Modules)
### Approach
Create `.py` files that mirror notebook structure:
```warp-runnable-command
src/mst_gis/pipeline/
├── phase0_setup.py          # CONFIG, TX, elevation seed
├── phase1_data_prep.py      # Land cover download/cache
├── phase2_batch_points.py   # Generate all points
├── phase3_batch_extract.py  # Extract elevation/landcover/zones
├── phase4_export.py         # Format and export
└── __init__.py
```
### Pros
* Mirrors notebook structure (easy to follow)
* Easy to understand progression
* Can run `python phase0_setup.py`, then `python phase1_data_prep.py`, etc.
* Clear 1:1 mapping between notebooks and code
### Cons
* Lots of duplicated code
* Not optimized for software architecture
* Each phase is a standalone script (no composition)
* Harder to reuse and test components
* State management between phases awkward
## Option 2: Production-Optimized Structure
### Approach
Create a true software library with clear abstractions:
```warp-runnable-command
src/mst_gis/pipeline/
├── __init__.py
├── config.py               # CONFIG management
├── data_preparation.py     # Data fetching/caching
├── point_generation.py     # Receiver point generation
├── data_extraction.py      # Elevation/landcover/zones
├── formatting.py           # CSV formatting
├── orchestration.py        # Coordinate all phases
└── workflow/
    ├── sequential.py       # Run phases 0->1->2->3->4
    └── parallel.py         # Future: parallel phases
```
### Pros
* Better separation of concerns
* Reusable functions
* Easier to test and maintain
* Can optimize individual components
* Foundation for parallelization
* Professional software structure
### Cons
* Doesn't directly mirror notebooks
* Slight learning curve (more abstractions)
* More up-front complexity
## Option 3: Both (Recommended)
### Approach
Create BOTH:
1. **Notebooks (Phase 0-4)**: For demonstration/exploration/teaching
2. **Modules (Option 2 structure)**: For production use
### Why This Works
* Notebooks show step-by-step workflow (educational)
* Modules provide optimized, reusable code (production)
* Can extract common code into a shared `utils/` module
* Each phase notebook can import from corresponding module
* User can either:
    * Follow notebooks for learning
    * Use Python modules for real work
    * Use command-line scripts for automation
### Structure
```warp-runnable-command
src/mst_gis/
├── pipeline/              # PRODUCTION CODE
│   ├── config.py
│   ├── data_preparation.py
│   ├── point_generation.py
│   ├── data_extraction.py
│   ├── formatting.py
│   ├── orchestration.py
│   └── __init__.py
├── propagation/          # EXISTING (KEEP)
│   └── profile_extraction.py
└── utils/               # SHARED UTILITIES
    ├── logging.py
    └── validation.py
data/notebooks/          # DEMONSTRATION
├── phase0_setup.ipynb
├── phase1_data_prep.ipynb
├── phase2_batch_points.ipynb
├── phase3_batch_extract.ipynb
└── phase4_export.ipynb
scripts/                 # COMMAND-LINE ENTRY POINTS
├── run_phase0_setup.py
├── run_phase1_dataprep.py
├── run_full_pipeline.py
└── run_profile_extraction.py
```
## Recommendation: Option 3 (Both)
### Phase 1 Implementation Plan
1. **Keep Phase 1 notebook** (already creating)
    * For demonstration
    * Shows API/caching concepts
    * Educational value
2. **Create `pipeline/` module structure** (after Phase 0-4 notebooks complete)
    * Core software library
    * Production-ready
    * Optimizable
    * Testable
3. **Create `scripts/` entry points**
    * Easy CLI usage
    * `python scripts/run_full_pipeline.py`
    * Wraps pipeline modules
### Benefits
1. **Educational**: Notebooks teach the concept
2. **Professional**: Modules provide production-ready code
3. **Reusable**: Modules can be imported elsewhere
4. **Testable**: Each module can be unit tested
5. **Extensible**: Easy to add parallelization, caching, etc.
6. **CLI**: Scripts provide command-line interface
## Timeline
### Immediate (This Week)
* Create Phase 0-4 notebooks (demonstration)
* These establish the workflow pattern
### Next (After notebooks work)
* Create `pipeline/` modules (production code)
* These are the actual optimized implementation
* Extract common code from notebooks
### Later (Once modules solid)
* Create `scripts/` for CLI entry points
* Add comprehensive tests
* Add parallelization
* Add caching layer
## Decision
**Proceed with Option 3: Create Both**
1. Continue with Phase 0-4 notebooks (demonstration)
2. After notebooks are working, create pipeline modules
3. This gives us the best of both worlds
Notebooks will serve as:
* Living documentation
* Tutorial for users
* Validation tool (run alongside modules)
Modules will serve as:
* Production-ready code
* Reusable components
* Basis for optimization
