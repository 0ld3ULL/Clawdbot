# [anthropics/anthropic-sdk-python] Release v0.76.0

**Source:** github
**URL:** https://github.com/anthropics/anthropic-sdk-python/releases/tag/v0.76.0
**Date:** 2026-02-10T14:57:21.586006
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates

## Summary

[TRENDING] Anthropic SDK update adds support for server-side tools, binary request streaming, and raw JSON schema in messages, expanding capabilities for AI agent architectures and interactions.

## Content

## 0.76.0 (2026-01-13)

Full Changelog: [v0.75.0...v0.76.0](https://github.com/anthropics/anthropic-sdk-python/compare/v0.75.0...v0.76.0)

### Features

* allow raw JSON schema to be passed to messages.stream() ([955c61d](https://github.com/anthropics/anthropic-sdk-python/commit/955c61dd5aae4c8a2c7b8fab1f97a0b88c0ef03b))
* **client:** add support for binary request streaming ([5302f27](https://github.com/anthropics/anthropic-sdk-python/commit/5302f2724c9890340c1b0dd042a1e670ed00eb93))
* **tool runner:** add support for server-side tools ([#1086](https://github.com/anthropics/anthropic-sdk-python/issues/1086)) ([1521316](https://github.com/anthropics/anthropic-sdk-python/commit/15213160a016a70538c81163c49ce5948fe06879))


### Bug Fixes

* **client:** loosen auth header validation ([5a0b89b](https://github.com/anthropics/anthropic-sdk-python/commit/5a0b89bb2c808cd0a413697a1141d4835ce00181))
* ensure streams are always closed ([388bd0c](https://github.com/anthropics/anthropic-sdk-python/commit/388bd0cbc53c4d8d8884d17a3051623728588eb4))
* **types:** allow pyright to infer TypedDict types within SequenceNotStr ([ede3242](https://github.com/anthropics/anthropic-sdk-python/commit/ede32426043273f9b31e70893207ad6519240591))
* use async_to_httpx_files in patch method ([718fa8e](https://github.com/anthropics/anthropic-sdk-python/commit/718fa8e62aa939dd8c5d46430aa1d1b05a5906d9))


### Chores

* add missing docstrings ([d306605](https://github.com/anthropics/anthropic-sdk-python/commit/d306605103649320e900ab3a2413d0dbd6b118c5))
* bump required `uv` version ([90634f3](https://github.com/anthropics/anthropic-sdk-python/commit/90634f3ef0a9d7ae5a1945f005b13aad245f6b32))
* **ci:** Add Claude Code GitHub Workflow ([#1293](https://github.com/anthropics/anthropic-sdk-python/issues/1293)) ([83d1c4a](https://github.com/anthropics/anthropic-sdk-python/commit/83d1c4aef1ae34b1aebe4ca25de8b0cd2d37a493))
* **deps:** mypy 1.18.1 has a regression, pin to 1.17 ([21c6374](https://github.com/anthro

## Analysis

Direct improvements to Claude API capabilities could significantly enhance The David Project's autonomous agent system, particularly the server-side tools and streaming features which enable more dynamic and flexible AI interactions.
