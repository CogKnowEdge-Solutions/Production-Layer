# CareMatch API - Spec-Driven Development Workflow

This project uses **Spec-Driven Development (SDD)** with GitHub Spec Kit to build the CareMatch API systematically.

## Workflow Phases

### Phase 1: Constitution 🏛️
Establish project principles and development guidelines.

```bash
/speckit.constitution Create principles focused on API quality, security, performance, and maintainability
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "constitution"
```

---

### Phase 2: Specification 📋
Define what the API should do (requirements, endpoints, data models).

```bash
/speckit.specify
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "specification"
```

---

### Phase 3: Technical Plan 🏗️
Create the implementation strategy with tech stack and architecture.

```bash
/speckit.plan
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "technical-plan"
```

---

### Phase 4: Task Breakdown 🎯
Generate actionable task list from the plan.

```bash
/speckit.tasks
```

**Optional - Convert to GitHub Issues:**
```bash
/speckit.taskstoissues
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "task-breakdown"
```

---

### Phase 5: Implementation 💻
Execute all tasks to build the API according to the plan.

```bash
/speckit.implement
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "implementation"
```

---

### Phase 6: Convergence ✅
Assess the codebase against spec/plan/tasks and append remaining work.

```bash
/speckit.converge
```

**Commit & Push:**
```bash
.specify/scripts/bash/push-phase.sh "convergence"
```

---

## Optional Enhancement Commands

### Clarification (Before Planning)
Ask structured questions to de-risk ambiguous areas.
```bash
/speckit.clarify
```

### Analysis (After Task Breakdown)
Cross-artifact consistency & coverage analysis.
```bash
/speckit.analyze
```

### Checklists (After Planning)
Generate quality checklists to validate requirements.
```bash
/speckit.checklist
```

---

## Project Structure

```
CareMatch/
├── .specify/                    # Spec Kit configuration
│   ├── memory/                 # Project memory (constitution, specs, etc.)
│   ├── templates/              # Artifact templates
│   ├── scripts/bash/
│   │   ├── push-phase.sh      # Automated push script
│   │   └── ...
│   └── workflows/              # Workflow definitions
├── .github/
│   ├── agents/                 # Agent command configs
│   └── prompts/                # Prompt templates
└── ... (implementation artifacts)
```

---

## Key Files to Track

After each phase, check for these artifacts in `.specify/memory/`:

- `constitution.md` - Project principles
- `specification.md` - API requirements & design
- `plan.md` - Technical implementation strategy  
- `tasks.md` - Actionable task list
- `implementation-log.md` - Build progress log

---

## Quick Commands Reference

| Phase | Command | Push |
|-------|---------|------|
| Constitution | `/speckit.constitution` | `.specify/scripts/bash/push-phase.sh "constitution"` |
| Specification | `/speckit.specify` | `.specify/scripts/bash/push-phase.sh "specification"` |
| Technical Plan | `/speckit.plan` | `.specify/scripts/bash/push-phase.sh "technical-plan"` |
| Task Breakdown | `/speckit.tasks` | `.specify/scripts/bash/push-phase.sh "task-breakdown"` |
| Implementation | `/speckit.implement` | `.specify/scripts/bash/push-phase.sh "implementation"` |
| Convergence | `/speckit.converge` | `.specify/scripts/bash/push-phase.sh "convergence"` |

---

## Getting Started

1. **Start in Claude Code with GitHub Copilot**
2. **Run Phase 1:** `/speckit.constitution`
3. **After each phase completes:**
   ```bash
   .specify/scripts/bash/push-phase.sh "phase-name"
   ```

---

## Notes

- The project is configured for **GitHub Copilot** integration
- All commits include co-authorship attribution
- Each phase builds on the previous one
- Push script handles git add/commit/push automatically
- If network issues occur during push, fix and retry manually

---

**Status:** 🟢 Ready for Phase 1 - Constitution
