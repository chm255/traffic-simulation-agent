# Experiment Rules

## Seed Rules

Simulation seeds must come from the user when the task requires user-specified seeds.

The LLM must not invent missing seeds.

A seed only affects processes that actually use randomness.


## Multi-Seed Experiments

For a multi-seed experiment, each seed corresponds to an independent SUMO simulation run.

The deterministic Python runtime is responsible for aggregating the results.


## Statistics

The current batch experiment statistics include:

- mean
- sample standard deviation
- minimum
- maximum

Sample standard deviation is calculated using Python statistics.stdev.


## Statistical Interpretation

A small number of seeds can only describe the observed variation in the tested runs.

The Agent must not claim statistical significance or strong robustness based only on a small number of simulation seeds.


## Deterministic Computation

Deterministic statistics should be calculated by Python rather than guessed or manually recomputed by the LLM.


## Dynamic Experiment Workflow

The current dynamic experiment workflow is:

initial seeds
→ run SUMO experiments
→ calculate average_queue sample standard deviation
→ compare the standard deviation with a user-provided threshold
→ run extra seeds only if the condition is satisfied

The runtime must validate the condition before allowing the extra experiment batch to execute.