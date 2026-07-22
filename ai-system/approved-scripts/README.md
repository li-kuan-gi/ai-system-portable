# Approved Scripts

This directory is the source of truth for agent-facing executable helper classification.

It does not carry hook installers, per-file command policy, credentials, or instance-specific tool configuration.

在 portable model 中，`approved-scripts/` 是安全網的 helper 分類面。安全網契約見 `ai-system/safety-net.md`；execution layer 可以消費這裡的分類，但不應把某個 runtime 的 permission table 反過來當成制度本體。

## Directories

- `allow/`: single-purpose helpers that do not change remote or shared persistent state. Examples include read-only inspection, validation, controlled local append, controlled local repo state changes, and controlled local git worktree helpers.
- `prompt/`: single-purpose helpers that need controlled confirmation or elevated handling before execution.
- `_lib/`: shared implementation used by public wrappers. Agents must not execute `_lib/` directly.
- `references/`: non-executable helper documentation or presets.

## Rules

- If a public helper in `allow/` or `prompt/` covers the need, use it instead of rebuilding a low-level command.
- `allow/` is the classification source of truth for approved helper execution. Execution hooks may consume this directory.
- `prompt/` helpers are not automatically allowed.
- Public helpers should be narrow, auditable, single-purpose, and explicit about impact.
- Do not put secrets, tokens, passwords, cookies, or credential values in this directory.
- Instance-specific helpers belong in the target workspace adapter, not in the portable core.
- Tool-specific helpers may be portable when they remain optional, cross-company,
  workspace-scoped, and free of account, environment, product, or target assumptions.

## Controlled Local Append

Controlled append helpers are a narrow exception to the usual "file write" risk. They may be in `allow/` only when they:

1. append only to an allowlisted local record file
2. validate required fields and evidence before writing
3. reject suspicious credential values
4. verify after writing that the previous content was preserved and only a tail block was added
5. do not call remote services or read credentials

Portable helpers:

- `allow/patchlog-append`
- `allow/friction-notes-append`

`patchlog-append` 只允許寫入：

- `ai-system/governance/patchlog.md`

## Package Boundary Validation

Package boundary validation helpers are read-only checks for portable package shape. They may be in `allow/` only when they:

1. inspect only local package paths
2. do not modify files, directories, git state, remotes, credentials, config, cache, sessions, or logs
3. ignore AI runtime mount points that are not package content
4. print only paths that require human or agent attention

Portable helpers:

- `allow/portable-boundary-scan`

## Controlled Git Worktree

Controlled git worktree helpers are a narrow exception for local repo isolation. They may be in `allow/` only when they:

1. operate only on repos inside the workspace root
2. create worktrees only under `.worktrees/<task>/<repo>/<slot>`
3. refuse to overwrite existing directories or symlinks
4. remove only clean managed worktrees
5. do not commit, push, change remotes, delete branches, or rewrite history

Portable helpers:

- `allow/git-worktree-add-detached`
- `allow/git-worktree-add-branch`
- `allow/git-worktree-remove-clean`
- `allow/git-pull-ff-only-clean`

`git-worktree-add-branch` accepts an optional `--branch <name>` override. The
helper validates the name with Git and still creates the worktree only under the
managed `.worktrees/<task>/<repo>/<slot>` path.

`git-pull-ff-only-clean` is a controlled local repo state change exception. It may stay in `allow/` only because it:

1. operates only on repos inside the workspace root
2. refuses to run when the worktree has tracked or untracked changes
3. uses only fast-forward pull
4. does not commit, push, change remotes, delete branches, merge with commits, rebase, or rewrite history
5. changes only local refs / worktree state for the selected repo

## Controlled Maven Verification

`allow/mvnw-check` runs a command-line allowlist of common Maven verification
goals only inside managed `.worktrees/` checkouts. It rejects unknown Maven
options, explicit deploy / image / service goals, custom settings / POM /
toolchain paths, secret-like property names, and `MAVEN_ARGS` injection.

This helper is not a code sandbox. The selected repository controls `mvnw`,
POMs, extensions, plugins, and tests. They may execute code, use the network,
read normal Maven settings, and update the default local dependency cache.
Use it only for a checkout whose code is already in task scope.

## GitHub PR Preflight

`allow/pr-preflight` produces a non-publishing GitHub PR readiness report for a
repository inside the workspace. It requires an exact configured remote and
derives the GitHub owner/repository from that remote instead of silently
switching targets. By default it does not fetch; `--fetch`
explicitly contacts that remote and updates local remote-tracking refs and
`FETCH_HEAD`. It never commits, pushes, creates or edits a PR, merges, or
triggers workflows.

## Local Conversation History

`allow/chat-history` reads Claude Code and Codex session formats only when the
recorded working directory is the installed workspace or one of its children.
It validates unambiguous session ID prefixes, bounds reads and output, and
applies best-effort sensitive-value redaction. Conversation history remains
private state: use this helper only after an explicit user request, and never
copy its raw output into the package.

## Adding Instance Helpers

Add instance-specific helpers only after deciding:

1. whether the helper is `allow` or `prompt`
2. what exact remote or local state it can touch
3. what output it may print
4. how it prevents secret leakage
5. where its usage is documented

Helpers that embed a specific account, tenant, host, namespace, environment,
product API, deployment target, or workspace-only workflow are adapter content.
