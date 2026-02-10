# [anthropics/anthropic-sdk-python] Release v0.77.0

**Source:** github
**URL:** https://github.com/anthropics/anthropic-sdk-python/releases/tag/v0.77.0
**Date:** 2026-02-10T14:57:21.584013
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates

## Summary

[TRENDING] Anthropic Python SDK v0.77.0 adds support for Structured Outputs in the Messages API, including new output configuration and custom JSON encoding, which could enhance structured response handling in AI agents and assistants.

## Content

## 0.77.0 (2026-01-29)

Full Changelog: [v0.76.0...v0.77.0](https://github.com/anthropics/anthropic-sdk-python/compare/v0.76.0...v0.77.0)

### Features

* **api:** add support for Structured Outputs in the Messages API ([ad56677](https://github.com/anthropics/anthropic-sdk-python/commit/ad5667774ad2e7efd181bcfda03fab3ea50630b9))
* **api:** migrate sending message format in output_config rather than output_format ([af405e4](https://github.com/anthropics/anthropic-sdk-python/commit/af405e473f7cf6091cb8e711264227b9b0508528))
* **client:** add custom JSON encoder for extended type support ([7780e90](https://github.com/anthropics/anthropic-sdk-python/commit/7780e90bd2fe4c1116d59bc0ad543aa609fc643d))
* use output_config for structured outputs ([82d669d](https://github.com/anthropics/anthropic-sdk-python/commit/82d669db652ed3d9aede61fd500fabb291b8f035))


### Bug Fixes

* **client:** run formatter ([2e4ff86](https://github.com/anthropics/anthropic-sdk-python/commit/2e4ff86d7b8bef8fe5c4b7e62bf47dfff79f0577))
* remove class causing breaking change ([#1333](https://github.com/anthropics/anthropic-sdk-python/issues/1333)) ([81ee953](https://github.com/anthropics/anthropic-sdk-python/commit/81ee9533d14f9dc3753a4a1320ea744825b17e92))
* **structured outputs:** avoid including beta header if `output_format` is missing ([#1121](https://github.com/anthropics/anthropic-sdk-python/issues/1121)) ([062077e](https://github.com/anthropics/anthropic-sdk-python/commit/062077e50d182719637403576f59761999b3b2f5))


### Chores

* **ci:** upgrade `actions/github-script` ([34df616](https://github.com/anthropics/anthropic-sdk-python/commit/34df6160ad386a7e8848e3435b22bd18bd726702))
* **internal:** update `actions/checkout` version ([ea50de9](https://github.com/anthropics/anthropic-sdk-python/commit/ea50de95bd1e43b8f00a45ef472330a3c8b396c8))

## Analysis

Direct updates to Claude SDK enable more precise structured output for The David Project and DEVA, potentially improving response parsing, type handling, and overall agent interaction reliability. The structured outputs feature is particularly relevant for creating more predictable and controlled AI interactions.
