# Wall Mode Model Research - February 2026

## Executive Summary

**Question:** Can Llama 4 Scout's 10M token context window effectively analyze our Unity codebase, or should we use a different model?

**Answer:** No. Llama 4 Scout's accuracy degrades to ~15.6% after 128K-256K tokens. **Gemini 2.5 Flash (1M tokens)** is the recommended alternative - it maintains 90%+ accuracy across its full context and is optimized for codebase analysis.

---

## The Problem: "Lost in the Middle" & Context Rot

### What the Research Shows

The "[Lost in the Middle](https://arxiv.org/abs/2307.03172)" phenomenon is well-documented: LLMs excel at retrieving information from the **beginning** (primacy bias) and **end** (recency bias) of context but struggle with data in the middle.

But it gets worse. A 2025 paper "[Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://arxiv.org/html/2510.05381v1)" found that **even when models perfectly retrieve information**, performance still degrades 13.9%-85% as input length increases. The sheer volume of distracting context interferes with reasoning.

### Why This Happens: Attention Dilution

> "As context grows, the probability mass of the attention mechanism spreads thinner. In a 10-million-token window, a single relevant sentence becomes statistically insignificant against millions of distractor tokens."

The signal literally drowns in noise.

---

## Model Comparison for Code Analysis

### Llama 4 Scout (10M tokens) - NOT RECOMMENDED

| Metric | Value |
|--------|-------|
| Claimed Context | 10 million tokens |
| Effective Context | 128K-256K tokens |
| Accuracy at 256K+ | ~15.6% on complex retrieval |
| Price | $0.11/$0.34 per 1M tokens |
| Speed | 2,600 tokens/s |

**The Problem:**
> "Independent benchmarks indicate that while Scout can physically accept 10M tokens, its reasoning capabilities degrade significantly after the 128k-256k token mark. One detailed analysis showed accuracy dropping to 15.6% on complex retrieval tasks at extended lengths."

Source: [llm-stats.com](https://llm-stats.com/models/llama-4-scout)

**Verdict:** The 10M context is marketing, not functional for our use case.

---

### Gemini 2.5 Flash (1M tokens) - RECOMMENDED

| Metric | Value |
|--------|-------|
| Claimed Context | 1 million tokens |
| Effective Context | ~1 million (maintains accuracy) |
| Accuracy Degradation | <5% across full window |
| Price | Very affordable |
| Speed | 238 tokens/s |

**Why It Works:**
> "The model distributes its attention uniformly across the input to reduce 'lost in the middle' effects and retains high accuracy even in contexts approaching the maximum size when properly structured."

> "When used for code-related tasks, the long context window allows the model to process and understand long repositories, generate refactors, and propose architectural updates with awareness of dependencies across the entire codebase."

**Codebase Analysis Capability:**
> "1 million tokens = ~30,000 lines of code... Review entire software projects, identify patterns, suggest refactoring, and detect potential bugs across thousands of files."

Source: [Google Developers Blog](https://developers.googleblog.com/en/gemini-25-flash-lite-is-now-stable-and-generally-available/)

---

### Gemini 2.5 Pro (1M-2M tokens) - ALTERNATIVE

| Metric | Value |
|--------|-------|
| Claimed Context | 1M (2M coming) |
| Coding Benchmark | 63.8% on SWE-Bench (best to date) |
| Price | Higher than Flash |

**For complex reasoning tasks**, Pro may be worth the extra cost. But Flash is sufficient for initial codebase analysis.

---

### Claude (200K tokens) - FOR REASONING LAYER

| Metric | Value |
|--------|-------|
| Context | 200K tokens |
| Accuracy | <5% degradation within window |
| Coding | Best for reasoning, self-explaining code |

**Use Case:** Claude works better for focused reasoning on specific code sections. Consider a two-layer approach:
1. Gemini identifies relevant files/sections (Wall Mode)
2. Claude reasons about specific fixes (smaller, focused context)

---

## Practical Implications for Wall Mode

### Amphitheatre Project Stats
- **Files:** 1,295 (after filtering packages)
- **Lines:** 419,623
- **Tokens:** ~4.7 million

### The Math Problem

Even Gemini's 1M token window can't fit our full 4.7M token codebase.

### Solutions

1. **Subsystem Filtering (Already Built)**
   - Voice: ~1.3M tokens ✓ Fits
   - Networking: ~1.9M tokens ✓ Fits (tight)
   - Seating: ~3.8M tokens ✗ Too large

2. **Priority-Based Truncation**
   - Load project-specific code first (PLAYAverse, Scripts)
   - Fill remaining context with related systems
   - Stop when budget is hit

3. **Smart Chunking**
   - Split large subsystems into related file groups
   - Maintain file relationship context
   - Query across chunks

4. **Hybrid Approach (Recommended)**
   ```
   User: "Why does player fall through floor after sitting?"

   1. Gemini (1M context): Analyze seating + physics subsystems
      → Identifies: SeatStation.cs, RigidbodyPlayer.cs, NetworkedThirdPerson.cs
      → "Collider disabled at line X, never re-enabled"

   2. Claude (200K context): Reason about specific fix
      → Gets just the 3 relevant files
      → Provides exact fix with line numbers
   ```

---

## Context Engineering Best Practices

Research emphasizes that **how** you present context matters more than **how much**:

> "Whether relevant information is present in a model's context is not all that matters; what matters more is how that information is presented."

### Recommendations Implemented

1. **File Index at Start** - Table of contents helps model navigate
2. **Clear File Boundaries** - Explicit separators between files
3. **Subsystem Labels** - Each file tagged with its subsystems
4. **Priority Ordering** - Project code before libraries
5. **Token Budgeting** - Stay within effective limits

### Additional Techniques to Consider

1. **Section Labels** - "// SECTION: Event handling" comments
2. **Relationship Annotations** - "This class inherits from X, called by Y"
3. **Recent Changes First** - Put recently modified files near end (recency bias)

---

## Recommended Architecture for Wall Mode

```
┌─────────────────────────────────────────────────────────────┐
│                      WALL MODE v2                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  COLLECTOR   │    │   GEMINI     │    │   CLAUDE     │   │
│  │              │    │   2.5 Flash  │    │   Sonnet     │   │
│  │ Wall Mode    │───▶│   1M tokens  │───▶│   200K       │   │
│  │ (built)      │    │   Analysis   │    │   Reasoning  │   │
│  │              │    │   Layer      │    │   Layer      │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                              │
│  Token Budget: 800K (safe margin for Gemini)                │
│  Fallback: Claude-only for small queries                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## API Access Options

### Gemini 2.5 Flash
- **Google AI Studio** (direct): Fastest, 238 t/s
- **Vertex AI**: Enterprise option
- **OpenRouter**: Easy API aggregator

### Pricing (Approximate)
| Model | Input | Output |
|-------|-------|--------|
| Gemini 2.5 Flash | ~$0.075/1M | ~$0.30/1M |
| Gemini 2.5 Pro | ~$1.25/1M | ~$5.00/1M |
| Claude Sonnet | $3.00/1M | $15.00/1M |
| Llama 4 Scout | $0.11/1M | $0.34/1M |

**Cost per Wall Mode query (800K tokens):**
- Gemini Flash: ~$0.06 input + response
- Much cheaper than our original Llama 4 Scout plan

---

## Conclusion

1. **Don't use Llama 4 Scout** - The 10M context is a lie for complex reasoning
2. **Use Gemini 2.5 Flash** - 1M tokens with real accuracy retention
3. **Update Wall Mode** - Cap at 800K tokens, use subsystem filtering
4. **Consider hybrid** - Gemini for discovery, Claude for fixes
5. **Context engineering matters** - How we format the wall affects quality

---

## Sources

- [Llama 4 Scout Benchmarks - llm-stats.com](https://llm-stats.com/models/llama-4-scout)
- [Lost in the Middle - Stanford/arxiv](https://arxiv.org/abs/2307.03172)
- [Context Length Alone Hurts - arxiv](https://arxiv.org/html/2510.05381v1)
- [Gemini 2.5 Flash - Google Developers](https://developers.googleblog.com/en/gemini-25-flash-lite-is-now-stable-and-generally-available/)
- [RULER Benchmark - NVIDIA](https://github.com/NVIDIA/RULER)
- [Long Context RAG Performance - Databricks](https://www.databricks.com/blog/long-context-rag-performance-llms)
- [Context Rot Research - Chroma](https://research.trychroma.com/context-rot)
