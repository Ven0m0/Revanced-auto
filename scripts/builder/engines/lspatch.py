"""LSPatch patching engine.

Ported from apk-tweak's lspatch engine.
Supports both binary CLI and JAR-based patching, module embedding,
and manager mode. Can run before ReVanced (complement) or replace it
(alternative) based on config.
"""

from __future__ import annotations
