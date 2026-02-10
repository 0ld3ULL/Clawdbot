# [anthropics/claude-code] Release v2.1.33

**Source:** github
**URL:** https://github.com/anthropics/claude-code/releases/tag/v2.1.33
**Date:** 2026-02-10T14:57:21.594018
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates, agent_memory

## Summary

[TRENDING] Claude Code v2.1.33 introduces advanced multi-agent workflow features like persistent memory scopes, teammate session management, and improved agent spawning controls. These updates provide direct architectural improvements for agentic system design and inter-agent communication.

## Content

## What's changed

- Fixed agent teammate sessions in tmux to send and receive messages
- Fixed warnings about agent teams not being available on your current plan
- Added `TeammateIdle` and `TaskCompleted` hook events for multi-agent workflows
- Added support for restricting which sub-agents can be spawned via `Task(agent_type)` syntax in agent "tools" frontmatter
- Added `memory` frontmatter field support for agents, enabling persistent memory with `user`, `project`, or `local` scope
- Added plugin name to skill descriptions and `/skills` menu for better discoverability
- Fixed an issue where submitting a new message while the model was in extended thinking would interrupt the thinking phase
- Fixed an API error that could occur when aborting mid-stream, where whitespace text combined with a thinking block would bypass normalization and produce an invalid request
- Fixed API proxy compatibility issue where 404 errors on streaming endpoints no longer triggered non-streaming fallback
- Fixed an issue where proxy settings configured via `settings.json` environment variables were not applied to WebFetch and other HTTP requests on the Node.js build
- Fixed `/resume` session picker showing raw XML markup instead of clean titles for sessions started with slash commands
- Improved error messages for API connection failures — now shows specific cause (e.g., ECONNREFUSED, SSL errors) instead of generic "Connection error"
- Errors from invalid managed settings are now surfaced
- VSCode: Added support for remote sessions, allowing OAuth users to browse and resume sessions from claude.ai
- VSCode: Added git branch and message count to the session picker, with support for searching by branch name
- VSCode: Fixed scroll-to-bottom under-scrolling on initial session load and session switch


## Analysis

Directly applicable to The David Project's autonomous agent system architecture, with specific enhancements for memory management, task coordination, and agent interaction patterns. The new hook events and memory scoping could significantly improve our current agent design.
