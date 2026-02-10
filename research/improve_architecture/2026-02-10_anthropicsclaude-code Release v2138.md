# [anthropics/claude-code] Release v2.1.38

**Source:** github
**URL:** https://github.com/anthropics/claude-code/releases/tag/v2.1.38
**Date:** 2026-02-10T14:57:21.587017
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates

## Summary

[TRENDING] Claude Code v2.1.38 provides several stability and security improvements for VS Code integration, including terminal behavior fixes, better bash command parsing, and sandbox mode protections. These updates enhance the reliability of AI coding assistants and plugin environments.

## Content

## What's changed

- Fixed VS Code terminal scroll-to-top regression introduced in 2.1.37
- Fixed Tab key queueing slash commands instead of autocompleting
- Fixed bash permission matching for commands using environment variable wrappers
- Fixed text between tool uses disappearing when not using streaming
- Fixed duplicate sessions when resuming in VS Code extension
- Improved heredoc delimiter parsing to prevent command smuggling
- Blocked writes to `.claude/skills` directory in sandbox mode


## Analysis

Directly relevant for The David Project's potential VS Code integration, improves AI coding assistant reliability, and provides insights into handling AI agent interactions in development environments. The security and parsing improvements could inform our own agent architecture design.
