# GEMINI.md

# Creative Workspace - AI Development Guide

## Project Philosophy

Creative Workspace is a desktop application for managing creative projects, assets, and documents.

The primary goal is long-term maintainability through clean architecture, modular services, and localized changes.

When making changes, prefer extending the existing architecture over introducing new patterns.

---

# Development Workflow

Before writing code:

1. Study the existing implementation.
2. Understand how the current architecture works.
3. Explain the proposed design.
4. Wait for approval.
5. Only then implement the feature.

Never begin coding immediately.

---

# Architecture

## MainWindow

MainWindow is an orchestrator.

Do not place business logic inside MainWindow.

MainWindow should coordinate services and UI only.

---

## Services

Business logic belongs in Services.

Before creating a new service:

- inspect existing services
- determine whether one already owns the responsibility
- justify introducing a new service

Do not create services simply because they "sound right."

---

## UI

UI components are presentation only.

Panels should:

- display data
- collect user input
- delegate work to services

Avoid filesystem logic or business logic inside widgets or panels.

---

## Event System

Use the existing event architecture when appropriate.

Avoid tightly coupling unrelated UI components.

---

## Folder Operations

Folder-related responsibilities belong in FolderService.

Do not expand FolderService into a general-purpose utility class.

---

## Thumbnail Generation

Thumbnail generation belongs in ThumbnailService.

Keep thumbnail logic isolated from asset management.

---

## Existing Code

Prefer extending existing implementations.

Avoid rewriting working systems.

Avoid large refactors unless explicitly requested.

Localized changes are preferred.

---

# Design Principles

Follow:

- Single Responsibility Principle
- High cohesion
- Low coupling
- Composition over duplication

---

# Before Creating New Classes

Always answer:

- Why is this class needed?
- Which existing responsibility is insufficient?
- Why can't an existing service be extended?

---

# Implementation Rules

When implementing:

- modify the fewest files necessary
- explain every modified file
- explain why each change is needed
- preserve backwards compatibility whenever practical

Do not rename files or move modules unless requested.

---

# Code Quality

Prefer:

- readable code
- explicit logic
- descriptive names

Avoid:

- unnecessary abstractions
- speculative architecture
- premature optimization

---

# When Unsure

Never guess.

Inspect the existing implementation first.

Base recommendations on the current code rather than filenames or assumptions.

---

# Communication Style

When proposing a feature:

1. Summarize your understanding.
2. Explain the design.
3. List affected files.
4. Explain trade-offs.
5. Wait for approval.

After implementation:

- summarize changes
- list modified files
- explain architectural impact
- suggest manual tests

---

# Project Goal

The objective is not to generate code quickly.

The objective is to build a clean, scalable application that can grow over many years.