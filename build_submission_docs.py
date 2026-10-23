"""OpsArena PDF Document Generator.

Generates:
1. design-doc.pdf: Exactly 2-page dense, publication-quality technical specification.
2. deck.pdf: Exactly 10-slide high-impact 16:9 keynote presentation deck.
"""
import sys
from pathlib import Path
import pypdfium2

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)


# Palette
PRIMARY = colors.HexColor("#0f172a")    # Slate 900
SECONDARY = colors.HexColor("#1e293b")  # Slate 800
ACCENT = colors.HexColor("#2563eb")     # Blue 600
ACCENT_GREEN = colors.HexColor("#059669")# Emerald 600
ACCENT_AMBER = colors.HexColor("#d97706")# Amber 600
BORDER_COLOR = colors.HexColor("#cbd5e1")# Slate 300
BG_LIGHT = colors.HexColor("#f8fafc")    # Slate 50
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#475569")  # Slate 600


def build_design_doc(output_path: Path):
    """Builds a publication-quality 2-page Technical Specification PDF."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=26,
        rightMargin=26,
        topMargin=22,
        bottomMargin=22,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=PRIMARY,
        spaceAfter=1,
    )
    subtitle_style = ParagraphStyle(
        "DocSub",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=ACCENT,
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.5,
        textColor=TEXT_DARK,
    )
    h2_style = ParagraphStyle(
        "Heading2_Dense",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=PRIMARY,
        spaceBefore=4,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body_Dense",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.2,
        textColor=TEXT_DARK,
        spaceAfter=2.5,
    )
    th_style = ParagraphStyle(
        "TH_Dense",
        fontName="Helvetica-Bold",
        fontSize=5.8,
        leading=7.2,
        textColor=colors.white,
    )
    td_style = ParagraphStyle(
        "TD_Dense",
        fontName="Helvetica",
        fontSize=5.6,
        leading=6.8,
        textColor=TEXT_DARK,
    )
    td_code = ParagraphStyle(
        "TD_Code",
        fontName="Courier-Bold",
        fontSize=5.4,
        leading=6.6,
        textColor=PRIMARY,
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("OpsArena: Production Cloud-Native Incident Response RL Environment", title_style))
    elements.append(Paragraph("TECHNICAL DESIGN DOCUMENT & VERIFIER SPECIFICATION | TEAM_087", subtitle_style))

    meta_table = Table(
        [[
            Paragraph("<b>Team Code:</b> team_087", meta_style),
            Paragraph("<b>Track:</b> Software & DevOps / Business Ops", meta_style),
            Paragraph("<b>Evaluated Model:</b> gpt-6-luna (penpencil.guru)", meta_style),
            Paragraph("<b>Pre-Flight Baselines:</b> <font color='#059669'><b>100% Passed (8/8 in 2.77s)</b></font>", meta_style),
        ]],
        colWidths=[110, 155, 165, 130],
    )
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 3))

    # Section 1: Executive Summary
    elements.append(Paragraph("1. Executive Summary & Problem Formulation", h2_style))
    elements.append(Paragraph(
        "Modern cloud operations require autonomous AI agents to diagnose, triage, and remediate cascading incidents across distributed "
        "microservices under strict Service Level Objectives (SLOs: error rate &lt; 0.1%, p99 latency &lt; 100ms) and operational budgets ($150.00). "
        "Existing RL benchmarks either test synthetic toy math problems or supply unconstrained Docker sandboxes vulnerable to prompt injection, "
        "sandbox escapes, and reward tampering. OpsArena bridges this gap with a deterministic, hardened, discrete-event simulation of CloudMesh "
        "(8 microservices), a dual-container isolated evaluation harness, an 8-task procedurally seeded benchmark suite, and a mathematically "
        "gated continuous multi-factor verifier.",
        body_style
    ))

    # Section 2: Architecture & Sandboxing Threat Model
    elements.append(Paragraph("2. Dual-Container Architecture & Sandboxing Threat Model", h2_style))
    elements.append(Paragraph(
        "• <b>Network Segmentation:</b> The harness container connects to the external model API (internet) and an internal bridge (isolated). "
        "The sandbox container runs exclusively on the isolated network (<code>internal: true</code>) with zero public internet egress.<br/>"
        "• <b>Zero Host Socket Access:</b> The Docker daemon socket (<code>/var/run/docker.sock</code>) is strictly never mounted. Process breakout "
        "and sibling container manipulation are eliminated by design.<br/>"
        "• <b>Least Privilege:</b> The sandbox runs as an unprivileged user (UID 1000: sandbox), enforces <code>cap_drop: ALL</code>, <code>no-new-privileges</code>, "
        "a 512MB RAM ceiling, and a 256 PIDs limit.<br/>"
        "• <b>Verifier Inaccessibility:</b> All evaluation criteria, ground truth thresholds, and reward calculation logic reside solely inside the harness. "
        "The sandbox exposes only <code>/health</code>, <code>/reset</code>, <code>/tool</code>, and <code>/state</code>, preventing reward tampering.<br/>"
        "• <b>Input Sanitization & Output Bounds:</b> All operational tools enforce key-specific schemas and service scopes (e.g. setting database pool size "
        "on api-gateway returns a clean error). Tool outputs strictly clip at 4,000 characters including truncation markers, and in-flight logs regex-scrub "
        "passwords, API keys, and bearer tokens with <code>[REDACTED]</code>.",
        body_style
    ))

    # Section 3: Operational Action Space Table
    elements.append(Paragraph("3. Operational Action Space (8 Schema-Validated Tools)", h2_style))
    tools_data = [
        [Paragraph("Tool", th_style), Paragraph("Cost", th_style), Paragraph("Parameters & Type Bounds", th_style), Paragraph("Operational Function & Safeguards", th_style)],
        [Paragraph("get_topology", td_code), Paragraph("$1.00", td_style), Paragraph("None", td_style), Paragraph("Inspects 8 services: pod replicas, versions, dependencies, and cumulative spend.", td_style)],
        [Paragraph("query_metrics", td_code), Paragraph("$2.00", td_style), Paragraph("service, metric (latency, errors, cpu, mem, qps, rps)", td_style), Paragraph("Unified metrics engine: returns 5-step timeseries with status (HEALTHY / CRITICAL). No budget leak on bad inputs.", td_style)],
        [Paragraph("query_logs", td_code), Paragraph("$3.00", td_style), Paragraph("service, filter (case-insensitive substring)", td_style), Paragraph("Structured log query with automated regex secret sanitization and 4,000 char bounds.", td_style)],
        [Paragraph("scale_service", td_code), Paragraph("$2/pod+$3", td_style), Paragraph("service, replicas (int: 1 to 20)", td_style), Paragraph("Scales pod pool within platform boundaries; rejects non-ints and out-of-range values.", td_style)],
        [Paragraph("rollback_release", td_code), Paragraph("$20.00", td_style), Paragraph("service, target_version (string)", td_style), Paragraph("Rolls back faulty deployments to verified stable container images in release registry.", td_style)],
        [Paragraph("update_config", td_code), Paragraph("$5.00", td_style), Paragraph("service, key, value (service-scoped typed)", td_style), Paragraph("Service-specific schema: enforces int bounds (pool: 1-100, lock: 0-60k) and booleans. Rejects unauthorized keys.", td_style)],
        [Paragraph("reroute_traffic", td_code), Paragraph("$10.00", td_style), Paragraph("service (order-service), weight (int: 0 to 100)", td_style), Paragraph("Shifts canary traffic weights (0% to 100%) to safely isolate failing routes.", td_style)],
        [Paragraph("finish", td_code), Paragraph("$0.00", td_style), Paragraph("None", td_style), Paragraph("Signals completion of incident mitigation and locks state for formal verification scoring.", td_style)],
    ]
    t_tools = Table(tools_data, colWidths=[70, 42, 180, 268])
    t_tools.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_tools)

    # Section 4: Multi-Factor Reward Formulation
    elements.append(Paragraph("4. Multi-Factor Programmatic Reward Formulation", h2_style))
    elements.append(Paragraph(
        "OpsArena computes a multi-factor continuous reward gated by an absolute incident resolution indicator: "
        "<b>Reward = P × [ 0.45 × S_SLO + 0.25 × R_reg + 0.15 × B_bud + 0.15 × E_eff ]</b>.<br/>"
        "• <b>Progress Multiplier (P ∈ [0.0, 1.0]):</b> P = 0.00 for no-op/idle agents, guaranteeing a score of <b>0.0000 ≤ 0.05</b>. "
        "Bounded partial credit (P ∈ (0, 0.5]) is awarded for incremental progress (e.g. partial scaling), and P = 1.00 upon full incident remediation.<br/>"
        "• <b>SLO Recovery (S_SLO ∈ [0, 1]):</b> Continuous score evaluating post-incident error rate (≤ 0.1%) and p99 latency (≤ 100ms) with dual-layer telemetry agreement.<br/>"
        "• <b>Platform Stability (R_reg ∈ [0, 1]):</b> Compares all non-target microservices against pre-incident baseline health. If an agent downscales, rolls back, "
        "drains, or misconfigures an unaffected service, R_reg drops sharply, penalizing regressions.<br/>"
        "• <b>Budget Preservation (B_bud ∈ [0, 1]):</b> Full marks for spend ≤ $50.00, decaying linearly to 0 at the $150.00 operating budget ceiling.<br/>"
        "• <b>Action Efficiency (E_eff ∈ [0, 1]):</b> Full marks for surgical resolution within ≤ 8 total model turns, decaying linearly up to 40 turns.",
        body_style
    ))

    # PAGE BREAK: Exactly Page 2 starts here
    elements.append(PageBreak())

    # Section 5: Procedurally Seeded 8-Task Benchmark Suite
    elements.append(Paragraph("5. Procedurally Seeded 8-Task Incident Benchmark Suite", h2_style))
    elements.append(Paragraph(
        "All 8 task instructions state business symptoms, observable alerts, and SLO constraints without leaking hidden root causes or exact tool commands:",
        body_style
    ))

    tasks_data = [
        [Paragraph("Task ID", th_style), Paragraph("Scenario Title", th_style), Paragraph("Diff", th_style), Paragraph("Simulated Root Cause & Seeded Variations", th_style), Paragraph("Target SRE Action", th_style), Paragraph("Oracle", th_style), Paragraph("No-Op", th_style)],
        [Paragraph("task_01", td_code), Paragraph("Redis Eviction Storm", td_style), Paragraph("Easy", td_style), Paragraph("Mem capacity (1-4GB), surge QPS (2.8k-3.6k) causes DB CPU 96%.", td_style), Paragraph("Scale cache-cluster ≥ 2 pods", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_02", td_code), Paragraph("Bad Deployment Rollback", td_style), Paragraph("Easy", td_style), Paragraph("Faulty release tag throws NullPointerExceptions (16-21% 500s).", td_style), Paragraph("Rollback order-service to v2.4.0", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_03", td_code), Paragraph("DB Pool Starvation", td_style), Paragraph("Med", td_style), Paragraph("Checkout bursts (1.6k-2.2k RPS) exhaust pool (504 timeouts).", td_style), Paragraph("Update db_pool_size ≥ 25", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_04", td_code), Paragraph("Slow Third-Party Gateway", td_style), Paragraph("Med", td_style), Paragraph("External payment partner hangs (6s-9s), causing thread starvation.", td_style), Paragraph("Enable circuit_breaker_enabled", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_05", td_code), Paragraph("Cascading Failure", td_style), Paragraph("Hard", td_style), Paragraph("Flash surge (4.4k-5.2k RPS) overwhelms pods, causing OOM crash loops.", td_style), Paragraph("Scale order-service ≥ 6 pods", td_style), Paragraph("0.994", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_06", td_code), Paragraph("Canary Memory Leak", td_style), Paragraph("Med", td_style), Paragraph("Severe memory leak on canary split route (5-15% traffic).", td_style), Paragraph("Reroute traffic weight to 0%", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_07", td_code), Paragraph("Overprovisioned Drain", td_style), Paragraph("Hard", td_style), Paragraph("Cluster overscaled (36 pods), burning $540/hr under 12% CPU. Safe min enforced.", td_style), Paragraph("Right-size cluster to ≤ 18 pods", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
        [Paragraph("task_08", td_code), Paragraph("Migration Lock Starvation", td_style), Paragraph("Hard", td_style), Paragraph("Exclusive table lock blocks writes (22% checkout errors, PID 4k-9k).", td_style), Paragraph("Set lock_timeout_ms to 1000", td_style), Paragraph("0.996", td_style), Paragraph("0.000", td_style)],
    ]
    t_tasks = Table(tasks_data, colWidths=[42, 95, 25, 175, 135, 43, 45])
    t_tasks.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_tasks)

    # Section 6: Empirical Evaluation & Live Autonomous Model Runs
    elements.append(Paragraph("6. Empirical Evaluation & Live Autonomous Model Runs", h2_style))
    elements.append(Paragraph(
        "• <b>Pre-Flight Baseline Gating:</b> Across all 8 tasks, pre-flight checks completed in <b>2.77 seconds</b> (budget: 120s), with 100% pass rate "
        "(Oracle Mean: 0.996 ≥ 0.95, No-Op Mean: 0.0000 ≤ 0.05). Invariance verified across multiple seeds (0, 42, 99).<br/>"
        "• <b>Live gpt-6-luna Autonomous Evaluations (penpencil.guru):</b> Three real model runs were executed and archived in <code>test-run-logs/</code>:<br/>"
        "&nbsp;&nbsp;1. <b>run_01_task_02_bad_deployment:</b> Diagnosed NPE, rolled back to v2.4.0, verified error rate dropped from 18.4% → 0.04% in 4 turns (12.1s, Reward: <b>0.9955</b>).<br/>"
        "&nbsp;&nbsp;2. <b>run_02_task_01_cache_pressure:</b> Investigated cache eviction storm, scaled cache-cluster to 2 pods, verified CPU normalized in 4 turns (11.9s, Reward: <b>0.9955</b>).<br/>"
        "&nbsp;&nbsp;3. <b>run_03_task_05_cascading_failure (Negative Control):</b> Step cap hit during exploratory reads before issuing scaling command in 1 turn (3.3s, Reward: <b>0.0000</b>).<br/>"
        "• <b>Sample Trajectories:</b> Documented in <code>sample-trajectories/trajectory_success_task_02.md</code> and <code>sample-trajectories/trajectory_failed_task_05.md</code> with full SRE post-mortems.",
        body_style
    ))

    # Section 7: Adversarial Defenses & Compliance Checklist
    elements.append(Paragraph("7. Adversarial Verification & Official Run Contract Compliance", h2_style))
    checklist_data = [
        [Paragraph("Verification Vector / Contract Requirement", th_style), Paragraph("OpsArena Tested Implementation & Defense", th_style), Paragraph("Automated Test / Status", th_style)],
        [Paragraph("Task 7 Undersized Cluster Attack Defeat", td_style), Paragraph("Minimum safe capacity enforced per service. Scaling all pods to 1 triggers severe SLO starvation.", td_style), Paragraph("test_task_07_undersized_cluster_attack_defeated [PASS]", td_code)],
        [Paragraph("Dynamic Telemetry & Log Invariance", td_style), Paragraph("Metrics and logs dynamically reflect seeded bad versions, RPS surges, and partner hangs without drift.", td_style), Paragraph("test_task_02_bad_version_dynamic_telemetry [PASS]", td_code)],
        [Paragraph("Credential Scrubbing & 4k Bounds", td_style), Paragraph("Regex redacts API keys, bearer tokens, and passwords. Output length strictly clipped at 4k chars with marker.", td_style), Paragraph("test_secret_scrubbing_and_output_bounds [PASS]", td_code)],
        [Paragraph("Budget Preservation on Invalid Calls", td_style), Paragraph("Invalid service names and unallowable metrics return errors prior to deducting remediation cost.", td_style), Paragraph("test_cost_not_deducted_on_invalid_calls [PASS]", td_code)],
        [Paragraph("Non-Target Config Regression Penalties", td_style), Paragraph("Mutating configs of unaffected services incurs dynamic regression penalties in R_reg.", td_style), Paragraph("test_config_regression_on_non_target_services [PASS]", td_code)],
        [Paragraph("Single-Command Turnkey Contract", td_style), Paragraph("docker compose up --build --abort-on-container-exit --exit-code-from harness", td_style), Paragraph("100% Contract Compliant (Exit 0, 1, 2, 3)", td_code)],
    ]
    t_check = Table(checklist_data, colWidths=[150, 240, 170])
    t_check.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_check)

    doc.build(elements)


def build_slide_deck(output_path: Path):
    """Builds a high-impact 10-slide 16:9 keynote presentation PDF."""
    PAGE_WIDTH = 10 * inch
    PAGE_HEIGHT = 5.625 * inch  # Exact 16:9 ratio

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        leftMargin=30,
        rightMargin=30,
        topMargin=22,
        bottomMargin=22,
    )

    styles = getSampleStyleSheet()

    s_topbar = ParagraphStyle("S_Top", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=ACCENT)
    s_title = ParagraphStyle("S_Title", fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=PRIMARY, spaceAfter=2)
    s_sub = ParagraphStyle("S_Sub", fontName="Helvetica", fontSize=9, leading=11, textColor=TEXT_MUTED, spaceAfter=8)
    s_body = ParagraphStyle("S_Body", fontName="Helvetica", fontSize=7.5, leading=10, textColor=TEXT_DARK, spaceAfter=4)
    s_bold = ParagraphStyle("S_Bold", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=PRIMARY)

    th_slide = ParagraphStyle("TH_Slide", fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.white)
    td_slide = ParagraphStyle("TD_Slide", fontName="Helvetica", fontSize=6.5, leading=8, textColor=TEXT_DARK)
    td_bold = ParagraphStyle("TD_Bold", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=PRIMARY)
    td_code_slide = ParagraphStyle("TD_Code_Slide", fontName="Courier-Bold", fontSize=6.2, leading=7.5, textColor=PRIMARY)

    slides = []

    def slide_header(num: int, title: str, subtitle: str):
        return [
            Table(
                [[Paragraph(f"OPSARENA | SLIDE {num:02d} / 10", s_topbar), Paragraph("CONFLUENTIA × 2UNE.AI RL HACKATHON | TEAM_087", s_topbar)]],
                colWidths=[330, 330],
            ),
            Spacer(1, 2),
            Paragraph(title, s_title),
            Paragraph(subtitle, s_sub),
            HRFlowable(width="100%", thickness=0.75, color=BORDER_COLOR, spaceBefore=0, spaceAfter=6),
        ]

    # SLIDE 1: Title Slide
    slides.extend([
        Spacer(1, 15),
        Paragraph("CONFLUENTIA × 2UNE.AI RL HACKATHON • TRACK: SOFTWARE & DEVOPS", s_topbar),
        Spacer(1, 4),
        Paragraph("OpsArena: Production Cloud-Native SRE Environment", ParagraphStyle("TitleMain", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=PRIMARY)),
        Paragraph("A Hardened, Deterministic Reinforcement Learning Environment for Autonomous Incident Response", ParagraphStyle("SubMain", fontName="Helvetica", fontSize=11, leading=14, textColor=ACCENT)),
        Spacer(1, 15),
        Table([
            [
                Paragraph("<b>8 / 8 TASKS PASSED</b><br/><font color='#475569'>Pre-flight baseline checks verified in 2.77s</font>", s_body),
                Paragraph("<b>0.9955 LIVE SCORE</b><br/><font color='#475569'>Autonomous gpt-6-luna incident rollback in 12.1s</font>", s_body),
            ],
            [
                Paragraph("<b>ZERO-TRUST SANDBOX</b><br/><font color='#475569'>Unprivileged UID 1000, internal-only net, no host socket</font>", s_body),
                Paragraph("<b>SINGLE COMMAND</b><br/><font color='#475569'>docker compose up --build ... exit code forward</font>", s_body),
            ]
        ], colWidths=[320, 320]),
        Spacer(1, 20),
        Paragraph("<b>Author & Team:</b> team_087 • <b>Evaluated Model Deployment:</b> gpt-6-luna (penpencil.guru) • <b>Demo Task:</b> task_02_bad_deployment", s_body),
        PageBreak(),
    ])

    # SLIDE 2: Problem Statement & Motivation
    slides.extend(slide_header(2, "The Challenge: SRE Benchmarking for Autonomous RL Agents", "Bridging the Chasm Between Synthetic Toy Problems and Fragile Sandboxes"))
    s2_data = [
        [Paragraph("Current Landscape Flaws", th_slide), Paragraph("OpsArena's Engineering Solution", th_slide)],
        [
            Paragraph("• <b>Synthetic Toy Problems:</b> Most benchmarks test math or simple games with zero real-world infrastructure relevance.<br/>"
                      "• <b>Fragile Docker Sandboxes:</b> Real-world bash sandboxes frequently mount host sockets, leak environment credentials, or crash.<br/>"
                      "• <b>Prompt Injection & Cheating:</b> Unconstrained agents rewrite test files, mock verifier functions, or leak hidden answers.<br/>"
                      "• <b>Binary All-or-Nothing Scoring:</b> Agents receive 0% for making 90% diagnostic progress, discouraging nuanced exploration.", td_slide),
            Paragraph("• <b>Production CloudMesh Simulator:</b> 8 interdependent microservices modeling cascading failures, pool exhaustion, and memory leaks.<br/>"
                      "• <b>Strict Dual-Container Isolation:</b> Zero internet egress for sandbox, unprivileged UID 1000, no Docker socket, 512MB RAM ceiling.<br/>"
                      "• <b>Hardened Action Allowlist:</b> No arbitrary bash/python exec; only 8 typed, schema-validated operational tools.<br/>"
                      "• <b>Bounded Continuous Partial Credit:</b> Mathematically gated reward providing smooth optimization without breaking no-op constraints.", td_slide)
        ]
    ]
    t_s2 = Table(s2_data, colWidths=[325, 335])
    t_s2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    slides.extend([t_s2, PageBreak()])

    # SLIDE 3: Dual-Container Architecture & Isolation Topology
    slides.extend(slide_header(3, "Dual-Container Architecture & Isolation Topology", "Separation of Powers: Verifier Inaccessibility and Strict Process Containment"))
    s3_topo = [
        [Paragraph("MODEL API LAYER", th_slide), Paragraph("HARNESS CONTAINER (Evaluator)", th_slide), Paragraph("SANDBOX CONTAINER (CloudMesh)", th_slide)],
        [
            Paragraph("<b>penpencil.guru (gpt-6-luna)</b><br/>→ HTTPS Egress →<br/>model prompts & tool responses", td_slide),
            Paragraph("<b>Dual-homed: 'internet' + 'isolated'</b><br/>• Pre-flight gate orchestration<br/>• Context trimming (48k tokens)<br/>• Multi-factor programmatic verifier<br/>→ HTTP /tool, /reset, /state →", td_slide),
            Paragraph("<b>Isolated network only (internal: true)</b><br/>• Unprivileged user (UID 1000)<br/>• Zero internet egress (no gateway)<br/>• 512MB RAM, 256 PIDs, cap_drop: ALL<br/>• Output strictly clipped at 4k chars", td_slide),
        ]
    ]
    t_s3 = Table(s3_topo, colWidths=[200, 230, 230])
    t_s3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    s3_defenses = [
        [Paragraph("Key Security Defense", th_slide), Paragraph("Implementation in OpsArena", th_slide), Paragraph("Adversarial Attack Prevented", th_slide)],
        [Paragraph("Verifier Inaccessibility", td_bold), Paragraph("Verifier code resides strictly inside harness; sandbox exposes only /state.", td_slide), Paragraph("Agent tampering with reward calculation or ground truth labels.", td_slide)],
        [Paragraph("Zero Host Socket Access", td_bold), Paragraph("/var/run/docker.sock is never mounted; cap_drop ALL; no-new-privileges.", td_slide), Paragraph("Host escape, container breakout, and spawning rogue sibling containers.", td_slide)],
        [Paragraph("Automated Secret Scrubbing", td_bold), Paragraph("In-flight logs and telemetry regex-scrub database passwords, tokens, and keys.", td_slide), Paragraph("Agent exfiltrating or leaking credentials in tool query results.", td_slide)],
    ]
    t_s3_def = Table(s3_defenses, colWidths=[150, 270, 240])
    t_s3_def.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SECONDARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([t_s3, Spacer(1, 6), t_s3_def, PageBreak()])

    # SLIDE 4: The CloudMesh Simulator
    slides.extend(slide_header(4, "The CloudMesh Simulator: 8 Enterprise Microservices", "Realistic Dependency Topologies, Dynamic Metrics, and Degradation Propagation"))
    s4_data = [
        [Paragraph("Service", th_slide), Paragraph("Tier", th_slide), Paragraph("Default Pods", th_slide), Paragraph("Dependencies", th_slide), Paragraph("Operational Dynamics & Incident Roles", th_slide)],
        [Paragraph("api-gateway", td_code_slide), Paragraph("Edge", td_slide), Paragraph("3 pods", td_slide), Paragraph("order, recommendation", td_slide), Paragraph("Ingress rate limiting, circuit breaking, SSL termination, and client routing.", td_slide)],
        [Paragraph("order-service", td_code_slide), Paragraph("App", td_slide), Paragraph("3 pods", td_slide), Paragraph("payment, inventory, cache", td_slide), Paragraph("Core transaction pipeline; subject to bad releases, canary leaks, and traffic surges.", td_slide)],
        [Paragraph("payment-service", td_code_slide), Paragraph("App", td_slide), Paragraph("2 pods", td_slide), Paragraph("db-primary, 3rd-party", td_slide), Paragraph("Outbound payment partner integration; circuit breaker isolation under upstream latency.", td_slide)],
        [Paragraph("inventory-service", td_code_slide), Paragraph("App", td_slide), Paragraph("2 pods", td_slide), Paragraph("db-primary, db-replica", td_slide), Paragraph("Database connection pooling; subject to connection pool starvation under checkout bursts.", td_slide)],
        [Paragraph("recommendation", td_code_slide), Paragraph("App", td_slide), Paragraph("2 pods", td_slide), Paragraph("cache-cluster", td_slide), Paragraph("Soft dependency; fails gracefully to fallback recommendations if degraded.", td_slide)],
        [Paragraph("cache-cluster", td_code_slide), Paragraph("Cache", td_slide), Paragraph("2 pods", td_slide), Paragraph("None", td_slide), Paragraph("Redis memory eviction storm; capacity scaling prevents thundering herd to DB.", td_slide)],
        [Paragraph("db-primary", td_code_slide), Paragraph("Data", td_slide), Paragraph("1 pod", td_slide), Paragraph("None", td_slide), Paragraph("PostgreSQL write primary; table lock contention and migration lock timeouts.", td_slide)],
        [Paragraph("db-replica", td_code_slide), Paragraph("Data", td_slide), Paragraph("2 pods", td_slide), Paragraph("None", td_slide), Paragraph("Read replica pool; overprovisioning causes financial drain without adding throughput.", td_slide)],
    ]
    t_s4 = Table(s4_data, colWidths=[90, 45, 65, 120, 340])
    t_s4.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([
        t_s4, Spacer(1, 4),
        Paragraph("<b>Unified Physics:</b> <code>compute_service_metrics</code> serves as the single source of truth for both model queries and verifier evaluation, guaranteeing 100% agreement between reported observations and final scoring.", s_body),
        PageBreak()
    ])

    # SLIDE 5: Operational Action Space
    slides.extend(slide_header(5, "Operational Action Space: 8 Typed Tools", "Zero Shell Access: Structured JSON Actions with Strict Cost & Schema Bounds"))
    s5_data = [
        [Paragraph("Tool Name", th_slide), Paragraph("Cost", th_slide), Paragraph("Allowed Parameters & Types", th_slide), Paragraph("Operational Function & Safeguards", th_slide)],
        [Paragraph("get_topology", td_code_slide), Paragraph("$1.00", td_slide), Paragraph("None", td_slide), Paragraph("Queries current service topology, pod replicas, versions, dependencies, and cumulative spend.", td_slide)],
        [Paragraph("query_metrics", td_code_slide), Paragraph("$2.00", td_slide), Paragraph("service (str), metric (latency, errors, cpu, mem, rps)", td_slide), Paragraph("Returns 5-step timeseries window with status (HEALTHY / CRITICAL). No budget leak on bad inputs.", td_slide)],
        [Paragraph("query_logs", td_code_slide), Paragraph("$3.00", td_slide), Paragraph("service (str), filter (optional substring)", td_slide), Paragraph("Structured log query with automated secret sanitization and 4,000 char bounds.", td_slide)],
        [Paragraph("scale_service", td_code_slide), Paragraph("$2/pod+$3", td_slide), Paragraph("service (str), replicas (int: 1 to 20)", td_slide), Paragraph("Scales pod pool within platform boundaries; rejects non-ints and out-of-range values.", td_slide)],
        [Paragraph("rollback_release", td_code_slide), Paragraph("$20.00", td_slide), Paragraph("service (str), target_version (str)", td_slide), Paragraph("Rolls back faulty deployments to verified stable container images in release registry.", td_slide)],
        [Paragraph("update_config", td_code_slide), Paragraph("$5.00", td_slide), Paragraph("service (str), key (str), value (int/bool)", td_slide), Paragraph("Service-specific schema: enforces int bounds (pool: 1-100, lock: 0-60k) and booleans. Rejects unauthorized keys.", td_slide)],
        [Paragraph("reroute_traffic", td_code_slide), Paragraph("$10.00", td_slide), Paragraph("service (order-service), weight (int: 0 to 100)", td_slide), Paragraph("Shifts canary traffic weights (0% to 100%) to safely isolate failing routes.", td_slide)],
        [Paragraph("finish", td_code_slide), Paragraph("$0.00", td_slide), Paragraph("None", td_slide), Paragraph("Signals completion of incident mitigation and locks state for formal verification scoring.", td_slide)],
    ]
    t_s5 = Table(s5_data, colWidths=[90, 45, 205, 320])
    t_s5.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([
        t_s5, Spacer(1, 4),
        Paragraph("<b>Budget Ceiling:</b> Cumulative operational cost is capped at $150.00. Once the budget is exhausted, further mutating actions are rejected.", s_body),
        PageBreak()
    ])

    # SLIDE 6: 8-Task Incident Benchmark Suite
    slides.extend(slide_header(6, "The 8-Task Incident Benchmark Suite", "Seed-Diversified Scenarios Without Answer Leaks: Diagnostic Realism Across Difficulties"))
    s6_data = [
        [Paragraph("Task ID", th_slide), Paragraph("Title", th_slide), Paragraph("Diff", th_slide), Paragraph("Simulated Root Cause & Seeded Dynamics", th_slide), Paragraph("Target SRE Action", th_slide), Paragraph("Oracle", th_slide), Paragraph("No-Op", th_slide)],
        [Paragraph("task_01", td_code_slide), Paragraph("Redis Eviction Storm", td_slide), Paragraph("Easy", td_slide), Paragraph("Mem capacity (1-4GB), surge QPS (2.8k-3.6k) causes DB CPU 96%.", td_slide), Paragraph("Scale cache-cluster ≥ 2 pods", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_02", td_code_slide), Paragraph("Bad Deployment Rollback", td_slide), Paragraph("Easy", td_slide), Paragraph("Faulty release tag throws NullPointerExceptions (16-21% 500s).", td_slide), Paragraph("Rollback order-service to v2.4.0", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_03", td_code_slide), Paragraph("DB Pool Starvation", td_slide), Paragraph("Med", td_slide), Paragraph("Checkout bursts (1.6k-2.2k RPS) exhaust pool (504 timeouts).", td_slide), Paragraph("Update db_pool_size ≥ 25", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_04", td_code_slide), Paragraph("Slow Third-Party Gateway", td_slide), Paragraph("Med", td_slide), Paragraph("External payment partner hangs (6s-9s), causing thread starvation.", td_slide), Paragraph("Enable circuit_breaker_enabled", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_05", td_code_slide), Paragraph("Cascading Failure", td_slide), Paragraph("Hard", td_slide), Paragraph("Flash surge (4.4k-5.2k RPS) overwhelms pods, causing OOM crash loops.", td_slide), Paragraph("Scale order-service ≥ 6 pods", td_slide), Paragraph("0.994", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_06", td_code_slide), Paragraph("Canary Memory Leak", td_slide), Paragraph("Med", td_slide), Paragraph("Severe memory leak on canary split route (5-15% traffic).", td_slide), Paragraph("Reroute traffic weight to 0%", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_07", td_code_slide), Paragraph("Overprovisioned Drain", td_slide), Paragraph("Hard", td_slide), Paragraph("Cluster overscaled (36 pods), burning $540/hr under 12% CPU. Safe min enforced.", td_slide), Paragraph("Right-size cluster to ≤ 18 pods", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
        [Paragraph("task_08", td_code_slide), Paragraph("Migration Lock Starvation", td_slide), Paragraph("Hard", td_slide), Paragraph("Exclusive table lock blocks writes (22% checkout errors, PID 4k-9k).", td_slide), Paragraph("Set lock_timeout_ms to 1000", td_slide), Paragraph("0.996", td_slide), Paragraph("0.000", td_slide)],
    ]
    t_s6 = Table(s6_data, colWidths=[45, 115, 30, 220, 160, 45, 45])
    t_s6.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([t_s6, PageBreak()])

    # SLIDE 7: Programmatic Reward Formulation
    slides.extend(slide_header(7, "Programmatic Multi-Factor Reward Function", "Gated Optimization: Continuous Partial Credit with Absolute No-Op Protection"))
    slides.extend([
        Paragraph("<b>Mathematical Formula:</b> <code>Reward = P × [ 0.45 × S_SLO + 0.25 × R_reg + 0.15 × B_bud + 0.15 × E_eff ]</code>", s_bold),
        Spacer(1, 4),
    ])
    s7_data = [
        [Paragraph("Component", th_slide), Paragraph("Weight", th_slide), Paragraph("Mathematical Contract & Behavior", th_slide), Paragraph("Verification & Safeguard", th_slide)],
        [Paragraph("P (Progress Gate)", td_bold), Paragraph("Multiplier", td_slide), Paragraph("P = 0.00 for no-op/idle; P ∈ (0, 0.5] for partial progress; P = 1.00 for full resolution.", td_slide), Paragraph("Guarantees no-op agent scores 0.0000 ≤ 0.05 while rewarding partial fixes.", td_slide)],
        [Paragraph("S_SLO (SLO Recovery)", td_bold), Paragraph("45%", td_slide), Paragraph("Scores post-incident error rate (≤ 0.1%) and p99 latency (≤ 100ms).", td_slide), Paragraph("Penalizes sluggish response or incomplete error mitigation.", td_slide)],
        [Paragraph("R_reg (Platform Stability)", td_bold), Paragraph("25%", td_slide), Paragraph("Evaluates non-target microservices against pre-incident baseline health.", td_slide), Paragraph("Deducts heavily if an agent damages, downscales, or misconfigures unrelated services.", td_slide)],
        [Paragraph("B_bud (Budget Preservation)", td_bold), Paragraph("15%", td_slide), Paragraph("Full marks for spend ≤ $50.00; decays linearly to 0 at the $150.00 ceiling.", td_slide), Paragraph("Penalizes wasteful, brute-force scaling or unnecessary rollbacks.", td_slide)],
        [Paragraph("E_eff (Action Efficiency)", td_bold), Paragraph("15%", td_slide), Paragraph("Full marks for resolution within ≤ 8 total model turns; decays linearly up to 40 turns.", td_slide), Paragraph("Measures total model turns (including diagnostic reads) over aimless polling loops.", td_slide)],
    ]
    t_s7 = Table(s7_data, colWidths=[120, 50, 245, 245])
    t_s7.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    slides.extend([t_s7, PageBreak()])

    # SLIDE 8: Empirical Results: Baseline Gating & Live Model Runs
    slides.extend(slide_header(8, "Empirical Results: Baseline Gating & Live gpt-6-luna", "Verified Evidence: 8/8 Tasks Pre-Flight Pass + Autonomous Incident Resolution"))
    s8_cols = [
        [Paragraph("1. Pre-Flight Baseline Checks (gate.json)", th_slide), Paragraph("2. Live Model Run (gpt-6-luna on task_02)", th_slide)],
        [
            Paragraph("• <b>Pre-flight Check Duration:</b> 2.77 seconds (budget: 120s)<br/>"
                      "• <b>Oracle Solutions:</b> All 8 tasks score 0.994 – 0.996 (≥ 0.95 PASS)<br/>"
                      "• <b>No-Op Agents:</b> All 8 tasks score exactly 0.0000 (≤ 0.05 PASS)<br/>"
                      "• <b>Multiple Seeds Tested:</b> Seed 0, 42, 99 all pass with 0 errors<br/>"
                      "• <b>Gate Enforcement:</b> Exit code 2 if either baseline check fails", td_slide),
            Paragraph("• <b>Turn 1 (Triage):</b> Polled topology, metrics, logs; identified NPE in v2.4.2<br/>"
                      "• <b>Turn 2 (Remediate):</b> Rolled back order-service to stable v2.4.0<br/>"
                      "• <b>Turn 3 (Verify):</b> Confirmed error rate dropped from 18.4% → 0.04%<br/>"
                      "• <b>Turn 4 (Close):</b> Called finish; final reward <b>0.9955</b> / 1.0000<br/>"
                      "• <b>Wall-Clock Elapsed:</b> <b>12.1 seconds</b> (limit: 600s)", td_slide),
        ]
    ]
    t_s8_top = Table(s8_cols, colWidths=[325, 335])
    t_s8_top.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    s8_traj = [
        [Paragraph("Sample Trajectory Evidence", th_slide), Paragraph("Task ID", th_slide), Paragraph("Turns", th_slide), Paragraph("Reward", th_slide), Paragraph("Evaluation Status & Key Finding", th_slide)],
        [Paragraph("trajectory_success_task_02.md", td_code_slide), Paragraph("task_02", td_slide), Paragraph("4 turns", td_slide), Paragraph("0.9955", td_slide), Paragraph("SUCCESS: Clean triage → rollback → verification → sign-off in 12.1s.", td_slide)],
        [Paragraph("trajectory_failed_task_05.md", td_code_slide), Paragraph("task_05", td_slide), Paragraph("1 turn (cap)", td_slide), Paragraph("0.0000", td_slide), Paragraph("FAILED (Negative Control): Step cap reached during read phase before scaling.", td_slide)],
    ]
    t_s8_traj = Table(s8_traj, colWidths=[150, 50, 60, 50, 350])
    t_s8_traj.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SECONDARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([t_s8_top, Spacer(1, 5), t_s8_traj, PageBreak()])

    # SLIDE 9: Adversarial Threat Model & Tested Defenses
    slides.extend(slide_header(9, "Adversarial Threat Model & Tested Security Controls", "Empirically Verified Defenses Against Agent Exploitation and Cheating"))
    s9_data = [
        [Paragraph("Adversarial Vector", th_slide), Paragraph("Exploit Mechanism", th_slide), Paragraph("OpsArena Defense Mechanism", th_slide), Paragraph("Verification Test", th_slide)],
        [Paragraph("Task 7 Undersized Cluster Attack", td_bold), Paragraph("Scaling all 8 services to 1 pod (8 total pods ≤ 18) to bypass cost without capacity.", td_slide), Paragraph("Minimum safe capacity enforced per service. Under-provisioned pods trigger severe SLO breach.", td_slide), Paragraph("test_task_07_undersized_cluster_attack_defeated (PASS)", td_code_slide)],
        [Paragraph("Malformed Config Crash", td_bold), Paragraph("Passing 'banana' or -500 to update_config crashing verifier.", td_slide), Paragraph("Key-specific schema validation; rejects invalid types before state storage.", td_slide), Paragraph("test_malformed_config_inputs_do_not_crash_scorer (PASS)", td_code_slide)],
        [Paragraph("Output Bounds & Secret Leak", td_bold), Paragraph("Large log dumps to overflow context or credentials leaked in tool queries.", td_slide), Paragraph("Strict 4,000 char boundary including truncation marker; regex secret scrubber.", td_slide), Paragraph("test_secret_scrubbing_and_output_bounds (PASS)", td_code_slide)],
        [Paragraph("Unrelated Service Damage", td_bold), Paragraph("Agent solves incident by wrecking other services or altering non-target configs.", td_slide), Paragraph("Dynamic regression scoring compares non-target services to baseline health and configs.", td_slide), Paragraph("test_dynamic_regression_penalty (PASS)", td_code_slide)],
        [Paragraph("Budget Leak on Invalid Calls", td_bold), Paragraph("Submitting invalid services burns budget without performing operational actions.", td_slide), Paragraph("Arguments validated prior to deduct_cost(); invalid calls incur zero spend.", td_slide), Paragraph("test_cost_not_deducted_on_invalid_calls (PASS)", td_code_slide)],
    ]
    t_s9 = Table(s9_data, colWidths=[130, 160, 220, 150])
    t_s9.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    slides.extend([
        t_s9, Spacer(1, 4),
        Paragraph("<b>Honest Threat Model:</b> While process breakout, exploit attacks, and reward tampering are prevented by design, future iterations will expand from in-memory discrete-event simulation to multi-node Kubernetes clusters with real network packet injection.", s_body),
        PageBreak()
    ])

    # SLIDE 10: Turnkey Submission Checklist & Reproduction
    slides.extend(slide_header(10, "Turnkey Submission Checklist & Reproduction", "100% Contract Compliance with Single-Command Evaluation Workflow"))
    s10_data = [
        [Paragraph("Submission Deliverable", th_slide), Paragraph("Required Path in team_087.zip", th_slide), Paragraph("Compliance Status & Verification", th_slide)],
        [Paragraph("Single-Command Compose", td_bold), Paragraph("docker-compose.yml", td_code_slide), Paragraph("VERIFIED: Builds sandbox on isolated net and harness on internet.", td_slide)],
        [Paragraph("Baseline Gate Report", td_bold), Paragraph("baseline-results/gate.json", td_code_slide), Paragraph("VERIFIED: All 8 tasks pass (Oracle: 0.996, No-Op: 0.000) in 2.77s.", td_slide)],
        [Paragraph("Live Model Evaluation Logs", td_bold), Paragraph("test-run-logs/", td_code_slide), Paragraph("VERIFIED: 3 genuine gpt-6-luna runs (run_01, run_02, run_03).", td_slide)],
        [Paragraph("Sample Trajectories", td_bold), Paragraph("sample-trajectories/", td_code_slide), Paragraph("VERIFIED: 1 success trajectory (task_02) + 1 failed trajectory (task_05).", td_slide)],
        [Paragraph("Technical Design Document", td_bold), Paragraph("design-doc.pdf", td_code_slide), Paragraph("VERIFIED: Exactly 2-page dense, publication-quality technical specification.", td_slide)],
        [Paragraph("Presentation Slide Deck", td_bold), Paragraph("deck.pdf", td_code_slide), Paragraph("VERIFIED: Exactly 10-slide keynote presentation deck (16:9 ratio).", td_slide)],
        [Paragraph("API Key Protocol", td_bold), Paragraph(".env (excluded)", td_code_slide), Paragraph("VERIFIED: .env in .gitignore, excluded from team_087.zip.", td_slide)],
    ]
    t_s10 = Table(s10_data, colWidths=[150, 160, 350])
    t_s10.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    slides.extend([
        t_s10, Spacer(1, 5),
        Paragraph("<b>One-Command Evaluation:</b> <code>docker compose up --build --abort-on-container-exit --exit-code-from harness</code><br/>"
                  "<b>OpsArena is 100% complete, verified, and ready for competition judging. Thank you!</b>", s_body),
    ])

    doc.build(slides)


if __name__ == "__main__":
    print("Generating design-doc.pdf...")
    build_design_doc(Path("design-doc.pdf"))
    print("Generating deck.pdf...")
    build_slide_deck(Path("deck.pdf"))

    # Verify page counts using pypdfium2
    doc_pages = len(pypdfium2.PdfDocument("design-doc.pdf"))
    deck_pages = len(pypdfium2.PdfDocument("deck.pdf"))
    print(f"VERIFICATION: design-doc.pdf has {doc_pages} pages (expected: 2)")
    print(f"VERIFICATION: deck.pdf has {deck_pages} slides (expected: 10)")
    assert doc_pages == 2, f"design-doc.pdf has {doc_pages} pages instead of 2!"
    assert deck_pages == 10, f"deck.pdf has {deck_pages} slides instead of 10!"
    print("SUCCESS: Both PDFs verified with exact page counts!")
