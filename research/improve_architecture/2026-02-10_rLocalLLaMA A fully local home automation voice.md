# [r/LocalLLaMA] A fully local home automation voice assistant using Qwen3 ASR, LLM and TTS on an RTX 5060 Ti with 16GB VRAM

**Source:** reddit
**URL:** https://reddit.com/r/LocalLLaMA/comments/1r0nd6m/a_fully_local_home_automation_voice_assistant/
**Date:** 2026-02-10T14:57:21.613824
**Relevance Score:** 10/10
**Priority:** high
**Goals:** improve_architecture, claude_updates, voice_assistant_development

## Summary

[TRENDING] A fully local, voice-controlled home automation assistant using Qwen3 models running entirely on local hardware, demonstrating low-latency voice interactions and integration with smart home systems. The project shows practical implementation of local ASR, LLM, and TTS with multiple tool integrations.

## Content

Video shows the latency and response times running everything Qwen3 (ASR&TTS 1.7B, Qwen3 4B Instruct 2507) with a Morgan Freeman voice clone on an RTX 5060 Ti with 16GB VRAM. In this example the SearXNG server is not running so it shows the model reverting to its own knowledge when unable to obtain web search information.

I tested other smaller models for intent generation but response quality dropped dramatically on the LLM models under 4B. Kokoro (TTS) and Moonshine (ASR) are also included as options for smaller systems.

The project comes with a bunch of tools it can use, such as Spotify, Philips Hue light control, AirTouch climate control and online weather retrieval (Australian project so uses the BOM). 

I have called the project "Fulloch". Try it out or build your own project out of it from here: [https://github.com/liampetti/fulloch](https://github.com/liampetti/fulloch)

Score: 104 | Comments: 16

## Analysis

Directly relevant for DEVA's voice assistant architecture, offers insights into local model performance, demonstrates multi-tool integration, and provides a reference implementation for voice-controlled AI agents with home automation capabilities. The local model approach and tool integration are particularly valuable for The David Project's autonomous agent design.
