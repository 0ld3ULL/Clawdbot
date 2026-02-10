# [r/LocalLLaMA] Femtobot: A 10MB Rust Agent for Low-Resource Machines

**Source:** reddit
**URL:** https://reddit.com/r/LocalLLaMA/comments/1r0or7s/femtobot_a_10mb_rust_agent_for_lowresource/
**Date:** 2026-02-10T14:57:21.617292
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates

## Summary

[TRENDING] A lightweight Rust-based AI agent framework designed for low-resource environments, demonstrating efficient agent architecture with minimal dependencies and small binary size. The project showcases techniques for creating compact, performant AI assistants with local memory and tool execution capabilities.

## Content

I wanted to run [OpenClaw](https://github.com/openclaw/openclaw)\-style workflows on very low-resource machines (older Raspberry Pis, cheap VPS instances), but most “lightweight” stacks still end up dragging in large runtimes and slow startup costs.

After trying [nanobot](https://github.com/HKUDS/nanobot) and seeing disk usage climb past \~350MB once Python, virtualenvs, and dependencies were installed, I rewrote the core ideas in Rust to see how small and fast it could be.

The result is [femtobot](https://github.com/enzofrasca/femtobot): a single \~10MB binary that currently supports:

* Telegram polling
* Local memory (SQLite + vector storage)
* Tool execution (shell, filesystem, web) via [rig-core](https://github.com/0xPlaygrounds/rig)

The implementation was done quickly with heavy AI assistance, so the code prioritizes simplicity and size over perfect Rust idioms. It works well on constrained hardware, but there are definitely rough edges.

Sharing in case it’s useful or interesting to others experimenting with small, local, or low-power agent setups. You are also welcome to contribute.

Repo: [https://github.com/enzofrasca/femtobot](https://github.com/enzofrasca/femtobot)

Score: 59 | Comments: 14

## Analysis

Directly relevant to The David Project's autonomous agent design, offering insights into minimalist agent architectures, efficient implementation strategies, and potential optimization techniques for resource-constrained environments. The Rust implementation and use of SQLite for memory management could inform our own agent development approach.
