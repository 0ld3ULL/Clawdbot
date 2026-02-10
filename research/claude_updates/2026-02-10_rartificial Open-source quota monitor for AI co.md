# [r/artificial] Open-source quota monitor for AI coding APIs - tracks Anthropic, Synthetic, and Z.ai in one dashboard

**Source:** reddit
**URL:** https://reddit.com/r/artificial/comments/1qz5aid/opensource_quota_monitor_for_ai_coding_apis/
**Date:** 2026-02-10T14:57:21.630855
**Relevance Score:** 10/10
**Priority:** high
**Goals:** claude_updates, improve_architecture

## Summary

[TRENDING] Open-source tool for tracking AI API usage across multiple providers with advanced quota monitoring and projection features. Provides local, lightweight solution for tracking API consumption and limits.

## Content


Every AI API provider gives you a snapshot of current usage. None of them show you trends over time, project when you will hit your limit, or let you compare across providers.

I built onWatch to solve this. It runs in the background as a single Go binary, polls your configured providers every 60 seconds, stores everything locally in SQLite, and serves a web dashboard.

What it shows you that providers do not:

- Usage history from 1 hour to 30 days
- Live countdowns to each quota reset
- Rate projections so you know if you will run out before the reset
- All providers side by side in one view

Around 28 MB RAM, no dependencies, no telemetry, GPL-3.0. All data stays on your machine.

https://onwatch.onllm.dev
https://github.com/onllm-dev/onWatch


Score: 13 | Comments: 6

## Analysis

Directly relevant for The David Project's API management, could help optimize Claude API usage, provides insights into potential quota constraints for AI-driven systems. Lightweight Go implementation makes it interesting for backend quota tracking.
