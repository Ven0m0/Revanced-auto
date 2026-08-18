- remove whatsapp_patcher rkpairip dtlx
- fix the build workflows. read "https://raw.githubusercontent.com/krvstek/uni-apks/refs/heads/main/.github/workflows/build.yml" for comparison
- add the patch pundles from @morphe_manager_settings.json
- use the patch selections from @morphe_all_selections-2026-08-18-072123.json
- use the [morphe jar cli](https://github.com/MorpheApp/morphe-desktop) patcher to patch apks. Revanced is outdated
- use java temurin 21 lts jre to patch
- add [morphe mcp](https://github.com/brosssh/morphe-mcp) to project claude config:
  ```bash
  claude mcp add --transport http morphe-mcp https://morphe-mcp.brosssh.com/mcp
  ```
  or in `.mcp.json`:
  ```json
  { "mcpServers": { "morphe-mcp": { "type": "http", "url": "https://morphe-mcp.brosssh.com/mcp" } } }
  ```

- cleanup and update the @docs/ . Remove stale infos and improve the github pages to reflect the curreny state of the repo
- use morphe-mcp to improve the patching process and to ensure everything works properly by actually verifying it
- improve the .claude/ folder by integrating these skills: "https://raw.githubusercontent.com/Paresh-Maheshwari/morphe-ai/refs/heads/main/.kiro/skills/morphe-faq/SKILL.md" "https://raw.githubusercontent.com/Paresh-Maheshwari/morphe-ai/refs/heads/main/.kiro/skills/tool-reference/SKILL.md""https://raw.githubusercontent.com/Paresh-Maheshwari/morphe-ai/refs/heads/main/.kiro/skills/dev-setup/SKILL.md" "https://raw.githubusercontent.com/Paresh-Maheshwari/morphe-ai/refs/heads/main/.kiro/skills/cli-reference/SKILL.md" https://github.com/Paresh-Maheshwari/morphe-ai/blob/main/.kiro/steering/build/morphe-cli.md
- fix renovate error:
  "Renovate failed to look up the following dependencies: Failed to look up pypi package ty: no-result. Files affected: pyproject.toml"
- fix the abandoned dependencies in issue 62
