# OpsArena: Production Cloud-Native Incident Response RL Environment

[![Confluentia Hackathon](https://img.shields.io/badge/Confluentia_×_2une.ai-RL_Hackathon-blue.svg)](https://github.com)
[![Track](https://img.shields.io/badge/Track-Software_%26_DevOps_/_Business_Ops-green.svg)](https://github.com)
[![Status](https://img.shields.io/badge/Pre--Flight_Baselines-ALL_PASSED_(8/8)-brightgreen.svg)](https://github.com)
[![Live Model Run](https://img.shields.io/badge/Live_gpt--6--luna-0.9955_Score-blue.svg)](https://github.com)
[![Team](https://img.shields.io/badge/Team-team__087-orange.svg)](https://github.com)

**OpsArena** is a production-grade Reinforcement Learning environment designed for evaluating autonomous AI agents on real-world Site Reliability Engineering (SRE) and cloud infrastructure incident response.

In OpsArena, an autonomous agent operates across **CloudMesh**, a distributed topology of 8 containerized microservices experiencing realistic production incidents (e.g., Redis eviction cascades, buggy canary rollouts, database connection pool exhaustion, slow third-party gateways, overscaled financial drains, and database migration table lock starvation).

The agent's objective is to diagnose root causes through telemetry and structured logs, execute surgical mitigations (scaling, rollbacks, traffic rerouting, configuration updates), restore Service Level Objectives (p99 latency < 100ms, error rate < 0.1%), preserve platform stability across non-target microservices, and adhere to an operational budget ceiling (\$150.00).

---

## 1. Architectural Highlights & Zero-Trust Sandboxing

OpsArena enforces strict network segmentation, complete process isolation, and programmatic reward integrity:

```
                           +------------------------------------------+
                           |           External Model API             |
                           |   (penpencil.guru / gpt-6-luna)          |
                           +--------------------+---------------------+
                                                ^
                                  HTTPS egress  |
                                                v
+-----------------------------------------------+-----------------------------------+
|  [Harness Container] (Evaluator)              |                                   |
|  - Evaluation Orchestrator                    |   Dual-Homed Network:             |
|  - Baseline Pre-flight Gate (Oracle & No-Op)  |   - 'internet' (outbound only)    |
|  - Programmatic Verifier & Scoring Logic      |   - 'isolated' (internal bridge)  |
|  - Token Trimming (48K) & Telemetry Logging   |                                   |
+-----------------------------------------------+-----------------------------------+
                                                ^
                   HTTP /tool, /reset, /state   |  (Internal Docker Bridge)
                   (No public port exposure)    v
+-----------------------------------------------+-----------------------------------+
|  [Sandbox Container] (CloudMesh Simulator)                                        |
|  - Unprivileged user (UID 1000: sandbox)                                          |
|  - Zero internet egress (`internal: true`, no default gateway)                     |
|  - In-memory discrete-event state machine (8 microservices)                       |
|  - Hard limits: 512MB RAM, 256 PIDs, drop ALL capabilities, no-new-privileges     |
|  - Output bounds: strictly clipped at 4,000 characters                            |
|  - Secret sanitization: passwords, API keys, and JWT tokens automatically redacted|
+-----------------------------------------------------------------------------------+
```

- **Zero Host Impact & Docker Denial**: The Docker socket (`/var/run/docker.sock`) is never mounted. The environment runs inside an unprivileged container without access to the host daemon or other containers.
- **Typed Action Allowlist & Key-Specific Schemas**: Eliminates arbitrary shell/python execution (`exec`, `bash`, `eval`). The model can only invoke 8 strictly typed, schema-validated operational actions. Every configuration key enforces key-specific integer bounds and boolean types, rejecting malformed inputs (e.g. string values for database pool sizes) before state storage.
- **Unified Physics & Ground Truth**: The `compute_service_metrics` engine serves as the single source of truth for both `query_metrics` observations and task verifiers, ensuring 100% agreement between reported telemetry and final scoring.
- **Reward Function Immunity**: The verifier code lives exclusively inside the harness container. The sandbox container does not host, know, or compute rewards, preventing reward tampering.

---

## 2. The 8 Deterministic Incident Tasks with Seeded Diversity

OpsArena features 8 seeded, deterministic incident families spanning Easy, Medium, and Hard operational challenges:

| Task ID | Title | Difficulty | Root Cause & Seeded Variations | Target SRE Action |
| :--- | :--- | :--- | :--- | :--- |
| `task_01_cache_pressure` | Redis Eviction Storm | Easy | Memory capacity (1-4GB), surge QPS (2.8k-3.6k) causes DB CPU 96% | Scale `cache-cluster` to $\ge 2$ replicas |
| `task_02_bad_deployment` *(Demo)* | Bad Release Rollback | Easy | Bad release tags throw NullPointerExceptions (16-21% 500s) | Roll back `order-service` to `v2.4.0` |
| `task_03_db_pool_exhaustion` | Connection Pool Starvation | Medium | Initial pool (3-8), checkout bursts (1.6k-2.2k RPS) exhaust connections | Update `db_pool_size` config to $\ge 25$ |
| `task_04_downstream_timeout` | Slow Third-Party Gateway | Medium | Hanging payment partner (6s-9s) causes thread starvation | Enable `circuit_breaker_enabled` on payment service |
| `task_05_cascading_failure` | Thundering Herd Cascade | Hard | Flash sale traffic surge (4.4k-5.2k RPS) causes OOM crash loop | Scale `order-service` to $\ge 6$ replicas |
| `task_06_canary_leak` | Memory Leak in Canary Route | Medium | Severe memory leak on canary split route (5-15% traffic) | Reroute traffic weight on canary to `0` |
| `task_07_cost_slo_rescue` | Overprovisioned Financial Drain | Hard | Platform overscaled (36 pods), burning \$540/hr under 12% CPU | Right-size gateway, order, and replica pods ($\le 18$) |
| `task_08_migration_lock` | Database Migration Schema Lock | Hard | Exclusive table lock on `order_items` blocks writes (22% errors) | Configure `lock_timeout_ms` to `1000` |

---

## 3. Operational Action Space (8 Tools)

Agents interact with the CloudMesh platform using 8 typed JSON tools:

1. `get_topology`: Returns topology graph, pod counts, versions, and current budget spent (\$1.00 cost).
2. `query_metrics`: Queries recent timeseries data for latency, error rate, CPU, memory, or throughput with full QPS/RPS alias support (\$2.00 cost).
3. `query_logs`: Queries structured application log tails with regex filtering and automated secret scrubbing (\$3.00 cost).
4. `scale_service`: Adjusts pod replica count between 1 and 20 pods with integer bounds verification (\$2/pod delta + \$3 cost).
5. `rollback_release`: Reverts a service to a previous stable container image verified against the release registry (\$20.00 cost).
6. `update_config`: Updates dynamic runtime configuration keys with key-specific type and range enforcement (\$5.00 cost).
7. `reroute_traffic`: Adjusts traffic split weight between 0% and 100% (\$10.00 cost).
8. `finish`: Concludes the incident mitigation and triggers formal verification scoring (\$0.00 cost).

---

## 4. Multi-Factor Programmatic Reward Formulation

The reward function enforces a strict zero-tolerance gate for no-op agents while providing continuous partial credit for incremental diagnostic progress:

$$\text{Total Reward} = P \times \left( 0.45 \cdot S_{\text{SLO}} + 0.25 \cdot R_{\text{reg}} + 0.15 \cdot B_{\text{bud}} + 0.15 \cdot E_{\text{eff}} \right)$$

- $P \in [0.0, 1.0]$: Remediation progress multiplier. For no-op or inactive agents, $P = 0.00$ guaranteeing an absolute score of **0.0000** ($\le 0.05$). For partial progress, $P \in (0.0, 0.5]$. Upon complete incident resolution, $P = 1.00$.
- $S_{\text{SLO}} \in [0, 1]$: Service Level Objective score based on post-mitigation error rate ($\le 0.1\%$) and p99 latency ($\le 100\text{ms}$).
- $R_{\text{reg}} \in [0, 1]$: Dynamic platform stability score penalizing pod crashes, downscaling, or disruption of non-target microservices.
- $B_{\text{bud}} \in [0, 1]$: Budget preservation score ensuring cumulative incident spend does not exceed \$150.00.
- $E_{\text{eff}} \in [0, 1]$: Efficiency score rewarding clean, targeted resolution within $\le 8$ actions.

---

## 5. Baseline Gate Verification Results

All 8 tasks have been verified against the official pre-flight gate contract:

```
task_01_cache_pressure       oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_02_bad_deployment       oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_03_db_pool_exhaustion   oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_04_downstream_timeout   oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_05_cascading_failure    oracle 0.99 [PASS]   no-op 0.00 [PASS]
task_06_canary_leak          oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_07_cost_slo_rescue      oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_08_migration_lock       oracle 1.00 [PASS]   no-op 0.00 [PASS]
```

- **Pre-Flight Execution Time**: **2.30 seconds** (budget: 120s).
- **Oracle Baseline**: **100% PASS** ($\ge 0.95$ across all tasks; mean: 0.999).
- **No-Op Baseline**: **100% PASS** ($0.0000 \le 0.05$ across all tasks).
- **Automated Test Suite**: **28 unit, integration, and adversarial tests** passing in 7.56s (`pytest tests/ -v`).

---

## 6. How to Run

### Single-Command Evaluation (Official Run Contract)

```bash
# 1. Configure environment variables in .env
cp .env.example .env
# Edit .env with your MODEL, API_KEY, and BASE_URL

# 2. Run single-command evaluation
docker compose up --build --abort-on-container-exit --exit-code-from harness
```

### Local Development & Testing

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit and integration tests
python -m pytest tests/ -v

# 3. Run baseline checks locally
MODE=baselines python -m harness.run

# 4. Run model on demo task
TASK_ID=task_02_bad_deployment MODE=full python -m harness.run
```

### Exit Code Protocol

- `0`: Model run succeeded / baselines passed.
- `1`: Model crashed or encountered execution failure.
- `2`: Baseline check failed (model was never called).
- `3`: Configuration error or invalid input file.

---

## 7. Submission Artifacts

- `baseline-results/gate.json`: Verifiable baseline report across all 8 tasks.
- `test-run-logs/`: Complete telemetry logs from three real model evaluations (`run_01_task_02_bad_deployment`, `run_02_task_01_cache_pressure`, `run_03_task_05_cascading_failure_failed`).
- `sample-trajectories/`: Step-by-step model trajectories with SRE post-mortems (`trajectory_success_task_02.md`, `trajectory_failed_task_05.md`).
- `design-doc.pdf`: 2-page publication-quality technical specification.
- `deck.pdf`: 10-slide keynote presentation deck.
- `team_087.zip`: Packaged submission archive ready for competition evaluation.
 origin/main
