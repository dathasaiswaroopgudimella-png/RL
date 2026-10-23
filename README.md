# OpsArena: Production Cloud-Native Incident Response RL Environment

[![Confluentia Hackathon](https://img.shields.io/badge/Confluentia_×_2une.ai-RL_Hackathon-blue.svg)](https://github.com)
[![Track](https://img.shields.io/badge/Track-Software_%26_DevOps_/_Business_Ops-green.svg)](https://github.com)
[![Status](https://img.shields.io/badge/Baseline_Checks-ALL_PASSED_(8/8)-brightgreen.svg)](https://github.com)
[![Team](https://img.shields.io/badge/Team-team__087-orange.svg)](https://github.com)

**OpsArena** is a production-grade Reinforcement Learning environment designed for evaluating autonomous AI agents on real-world Site Reliability Engineering (SRE) and cloud infrastructure incident response.

In OpsArena, an autonomous agent manages **CloudMesh**, a distributed topology of 8 containerized microservices experiencing realistic production incidents (e.g., Redis eviction cascades, buggy canary rollouts, database connection pool exhaustion, slow third-party gateways, and overscaled financial drains).

The agent's objective is to diagnose root causes through telemetry and structured logs, execute surgical mitigations (scaling, rollbacks, traffic rerouting, configuration updates), restore Service Level Objectives (p99 latency < 100ms, error rate < 0.1%), preserve platform stability, and adhere to an operational budget ceiling (\$150.00).

---

## 1. Architectural Highlights & Sandboxing

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
|  [Harness Container]                          |                                   |
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
- **Typed Action Allowlist**: Eliminates arbitrary shell/python execution (`exec`, `bash`, `eval`). The model can only invoke 8 strictly typed, schema-validated operational actions.
- **Reward Function Immunity**: The verifier code lives exclusively inside the harness container. The sandbox container does not host, know, or compute rewards, preventing reward tampering.

---

## 2. The 8 Deterministic Incident Tasks

OpsArena features 8 seeded, deterministic incident families spanning Easy, Medium, and Hard operational challenges:

| Task ID | Title | Difficulty | Root Cause | Target Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| `task_01_cache_pressure` | Redis Eviction Storm | Easy | Cache memory eviction storm spikes DB CPU to 96% | Scale `cache-cluster` to $\ge 2$ replicas |
| `task_02_bad_deployment` *(Demo)* | Bad Release Rollback | Easy | Regression in `v2.4.1` throws NPE (18.4% errors) | Roll back `order-service` to `v2.4.0` |
| `task_03_db_pool_exhaustion` | Connection Pool Starvation | Medium | Checkout traffic exhausts DB connection pool | Update `db_pool_size` config to $\ge 25$ |
| `task_04_downstream_timeout` | Slow Third-Party Gateway | Medium | Hanging payment partner threads out gateway | Enable `circuit_breaker_enabled` on payment service |
| `task_05_cascading_failure` | Thundering Herd Cascade | Hard | Flash sale traffic causes OOM crash loop | Scale `order-service` to $\ge 6$ replicas |
| `task_06_canary_leak` | Memory Leak in Canary Route | Medium | Memory leak in 10% canary traffic route | Reroute traffic weight on canary to `0` |
| `task_07_cost_slo_rescue` | Overprovisioned Financial Drain | Hard | Platform overscaled (36 pods), burning \$450/hr | Right-size gateway, order, and replica pods ($\le 18$) |
| `task_08_migration_lock` | Database Migration Schema Lock | Hard | Exclusive table lock on `order_items` blocks writes | Configure `lock_timeout_ms` to `1000` |

---

## 3. Operational Action Space (8 Tools)

Agents interact with the CloudMesh platform using 8 typed JSON tools:

1. `get_topology`: Returns topology graph, pod counts, versions, and current budget spent (\$1.00 cost).
2. `query_metrics`: Queries recent timeseries data for latency, error rate, CPU, memory, or QPS (\$2.00 cost).
3. `query_logs`: Queries structured application log tails with optional substring filter (\$3.00 cost).
4. `scale_service`: Adjusts pod replica count between 1 and 20 pods (\$2/pod delta + \$3 cost).
5. `rollback_release`: Reverts a service to a previous stable container image (\$20.00 cost).
6. `update_config`: Updates dynamic runtime configuration keys with validation (\$5.00 cost).
7. `reroute_traffic`: Adjusts traffic split weight between 0% and 100% (\$10.00 cost).
8. `finish`: Concludes the incident mitigation and triggers formal verification scoring (\$0.00 cost).

---

## 4. Multi-Factor Programmatic Reward Function

The reward function enforces a strict zero-tolerance gate: if the primary incident condition is not mitigated ($P = 0$), the total score is **0.0000**, guaranteeing the no-op check passes ($\le 0.05$).

$$\text{Total Reward} = P \times \left( 0.45 \cdot S_{\text{SLO}} + 0.25 \cdot R_{\text{reg}} + 0.15 \cdot B_{\text{bud}} + 0.15 \cdot E_{\text{eff}} \right)$$

- $P \in \{0, 1\}$: Binary incident resolution indicator.
- $S_{\text{SLO}} \in [0, 1]$: Service Level Objective score based on post-mitigation error rate ($\le 0.1\%$) and p99 latency ($\le 100\text{ms}$).
- $R_{\text{reg}} \in [0, 1]$: Platform stability score penalizing pod crashes or outages on unrelated microservices.
- $B_{\text{bud}} \in [0, 1]$: Budget preservation score ensuring cumulative incident spend does not exceed \$150.00.
- $E_{\text{eff}} \in [0, 1]$: Efficiency score rewarding clean, targeted resolution within $\le 8$ actions.

---

## 5. Baseline Gate Verification Results

All 8 tasks have been verified against the official pre-flight gate contract:

```
task_01_cache_pressure       oracle 0.99 [PASS]   no-op 0.00 [PASS]
task_02_bad_deployment       oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_03_db_pool_exhaustion   oracle 0.99 [PASS]   no-op 0.00 [PASS]
task_04_downstream_timeout   oracle 0.99 [PASS]   no-op 0.00 [PASS]
task_05_cascading_failure    oracle 0.98 [PASS]   no-op 0.00 [PASS]
task_06_canary_leak          oracle 0.99 [PASS]   no-op 0.00 [PASS]
task_07_cost_slo_rescue      oracle 1.00 [PASS]   no-op 0.00 [PASS]
task_08_migration_lock       oracle 0.99 [PASS]   no-op 0.00 [PASS]
```

- **Pre-Flight Execution Time**: **3.28 seconds** (budget: 120s).
- **Oracle Baseline**: **100% PASS** ($\ge 0.95$ across all tasks).
- **No-Op Baseline**: **100% PASS** ($0.00 \le 0.05$ across all tasks).

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
- `test-run-logs/`: Complete telemetry logs from live `gpt-6-luna` run.
- `sample-trajectories/`: Step-by-step model trajectory (`trajectory_task_02.md`).
- `design-doc.pdf`: 2-page system architecture and reward design document.
- `deck.pdf`: Presentation slide deck for final judging.
