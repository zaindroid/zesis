# 06 — Simulations

- `security_selection/` — single-robot battery-aware PQC security-level
  selection: does it need RL, or do principled heuristics suffice?
  (four-policy comparison; the #3→#4 gap is the headline).
- `swarm/` — coordinated-deadline swarm (N=5) + the RL-convergence and
  N-scaling verification checks (VERIFY_REPORT).

Pure simulations with real measured cost inputs. Code:
`codebase/security_selection_sim/`, `codebase/swarm_coordination_sim/`.
