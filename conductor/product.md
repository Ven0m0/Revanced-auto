# Product Guide

## Initial Concept
Automated APK patching and building system for ReVanced and RVX (ReVanced Extended) applications.

## Vision
To provide a robust, stable, and automated system for patching Android applications using ReVanced, catering specifically to advanced users and automated CI/CD environments. The system prioritizes reliability and correctness over speed, ensuring consistent builds across different environments.

## Target Audience
-   **Advanced Users:** Individuals capable of configuring build parameters and troubleshooting basic environment issues to create custom patched APKs.
-   **CI/CD Pipelines:** Automated systems (like GitHub Actions) that require a scriptable, reliable tool for scheduled or on-demand builds.

## Core Features & Priorities
1.  **Automated Patching:** Seamless integration with ReVanced CLI to apply custom patch bundles to target APKs.
2.  **Multi-Source Downloading:** Reliable fetching of stock APKs from multiple resilient sources (APKMirror, Uptodown, Archive.org) with fallback logic.
3.  **CI/CD Integration:** First-class support for GitHub Actions, enabling daily scheduled builds and manual workflow triggers.
4.  **Build Caching:** Intelligent caching of dependencies and build artifacts to optimize resource usage without compromising build integrity.
5.  **Observability:** Comprehensive logging and error reporting to facilitate debugging and status monitoring.

## Key Constraints
-   **Strict CLI Adherence:** The system must strictly align with specific versions and requirements of the ReVanced CLI to ensure patch compatibility.
-   **Minimal Dependencies:** The runtime environment should remain lightweight, minimizing external dependencies to ensure portability and ease of setup.
