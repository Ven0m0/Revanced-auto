# Product Guidelines

## Code Structure & Maintainability
-   **Modular Design:** The codebase must adhere to a modular architecture. Core logic should be separated into distinct, reusable library files located in the `lib/` directory (e.g., `lib/network.sh`, `lib/patching.sh`).
-   **Separation of Concerns:** Each script or module should have a single, well-defined responsibility. The main build script (`build.sh`) should act purely as an orchestrator, delegating specific tasks to the library modules.
-   **Reusability:** Functions should be designed to be reusable across different parts of the system where possible, avoiding code duplication.

## Error Handling Philosophy
-   **Fail Fast:** The system must adopt a "fail fast" approach. Upon encountering any critical error (e.g., missing dependency, network failure after retries, patch error), the process must terminate immediately.
-   **Descriptive Output:** Errors must be logged explicitly to `stderr` with clear, descriptive messages explaining the cause of the failure.
-   **Non-Zero Exit Codes:** The system must exit with a non-zero status code upon failure to correctly signal the error to calling processes (e.g., CI/CD pipelines).

## Configuration Management
-   **Graceful Degradation:** While configuration validity is important, the system should prioritize resilience. If non-critical configuration issues are encountered (e.g., deprecated keys, missing optional values), the system should issue a warning log and fall back to safe, sensible defaults rather than crashing.
-   **User Feedback:** Clear warnings should be displayed to the user when defaults are applied, encouraging them to update their configuration without blocking their immediate goal.

## Documentation Standards
-   **Centralized Documentation:** Documentation should be primarily maintained in dedicated Markdown files within the `docs/` directory. This includes feature guides, configuration references, and troubleshooting steps.
-   **Clean Code:** Code comments should be kept to a minimum, focusing on explaining complex logic or "why" a decision was made, rather than describing "what" the code is doing. The code itself should be self-documenting through clear variable and function naming.
