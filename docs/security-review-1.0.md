# Security review before 1.0.0

Reviewed 2026-11-14 on `master` as of 0.14.0 (commit 1331e16), before the
1.0.0 release and the Omarchy plugin marketplace listing. A review, not an
audit or a guarantee: it looked for issues someone could exploit and fixed
what it found. [SECURITY.md](../SECURITY.md) is the standing privilege
model; this page records what was checked and why it changed.

## Scope

The whole tracked repo: the watcher and CLI (`omatrophy.py`), the stores
(`stores/`), guides (`guides.py`, `guide_maker.py`, `guide_agents.py`,
`guide_bench.py`, `prompts/guide/`), by-hand state (`by_hand.py`), the
Guide key (`guide_key.py`), the platinum image (`share.py`,
`PlatinumShare.qml`), every QML view and entry point, `dev/` and `tools/`
scripts, CI, and the repo's hygiene.

## Threat model

OmaTrophy runs unsandboxed as the user, like every Omarchy plugin. A local
process running as the user can already do anything the user can, so it is
not the attacker here. The attackers are whoever controls data OmaTrophy
reads and acts on:

- **Web pages** the guide maker's agent reads, and through it the agent's
  answers (prompt injection).
- **Guide files someone shares** (`guide import`).
- **Store data**: Steam's schema (game developers write achievement names
  and descriptions), Steam's web answers, Comet's database and Heroic's
  library cache (GOG's API and those programs write them).

## Method

- Read every module for: commands built from data (shell use, argument
  injection), file paths built from data (traversal, links), writes under
  state, cache and config, network calls (hosts, schemes, redirects,
  timeouts, sizes), parsing of untrusted files, the Hyprland Lua the
  Steam loader and Guide key send, and QML that shows or loads data.
- Checked suspicions on a throwaway offscreen Quickshell with a local HTTP
  server logging requests (never the live shell): which `Text` formats
  fetch images, and whether the tracker's Markdown filter held.
- Ran the marketplace's own static baseline
  (`omacom/omarchy-plugin-marketplace` at f2732ad,
  `security-baseline-analysis.mjs`) over the tracked files, with a
  `curl | sh` positive control to show the harness catches findings.

## Findings and fixes

Each fix has a regression test; `python3 -m unittest discover -s tests`.

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | Medium | **Server-side request forgery in the guide maker.** OmaTrophy fetched every `https` URL the agent cited, and the agent cites what the pages it reads tell it to. A page could make OmaTrophy send GET requests to the owner's router, another LAN device, `localhost` services or cloud metadata (`169.254.169.254`), and fold the answer into the guide's sources. | `guide_maker.fetch_page` refuses `localhost` and IP literals off the public internet, and a connection class checks the address the socket actually reached (after DNS, on every redirect), so a public name that resolves to a private address is refused too. Tests: `test_fetch_refuses_hosts_off_the_public_internet`, `test_public_address`, `test_connection_refuses_a_name_that_resolves_to_a_private_address`. |
| 2 | Low (privacy) | **Images in guide prose were fetched.** Qt's `MarkdownText` loads an image's URL, plain `http` included, as soon as the prose shows. The tracker's filter removed only `![alt](url)` without `]` in the alt, so `![a [b] c](url)`, reference images (`![x][r]`) and `!![x](url)` still loaded: a beacon in an agent's or a shared guide's prose told its owner when and from where it was read. SECURITY.md said images were not loaded. | `guides.no_images` drops every `!` before a `[` and every `<img>` in notes, sections and walkthrough text; the tracker's `safeMarkdown` does the same. Tests: `test_no_images_turns_every_image_into_a_link`, `test_answer_prose_carries_no_images`, `test_only_prose_is_markdown_and_it_goes_through_safe_markdown`. |
| 3 | Low (privacy) | **HTML rendered in panel and tracker labels.** The `Caption` and `MiniLabel` components were left on `AutoText`, which renders a string that looks like HTML; they show achievement descriptions, guide tips, missable notes and game names. An `<img src="http://...">` in a developer's achievement text or a guide was fetched when the panel opened. | Both components are `PlainText`. A test checks every `Text` in every `.qml` file sets its format, and that only the guide prose is Markdown: `test_every_text_sets_its_format`. |
| 4 | Low | **Image URLs off the stores' hosts reached the shell.** `cached()` handed back any URL it refused to fetch, the panel's image rewrite kept such URLs, and GOG's cover came straight from Heroic's cache, so the shell loaded URLs from any host, `http` too. SECURITY.md says only the stores' HTTPS hosts are contacted. | `stores.base.shown_image` passes only `file://` and trusted `https` URLs; `cached()`, `local_images`, `platinum_event` and `Gog.art` use it. Tests: `ShownImages`, `test_a_cover_off_gogs_hosts_is_not_handed_to_the_shell`, the updated `test_untrusted_urls_are_never_fetched`. |
| 5 | Low | **`guide import` followed links.** A shared folder (an unpacked archive) could hold `x.md` as a link to one of the owner's files; its text was copied into the guides folder, where the next make puts sources into the agent's prompt. Files of any size were copied, and a link already in the guides folder was written through. | Only plain files of at most 16 MB are copied (`os.lstat`), each through a temporary file and a rename. Tests: `test_links_in_the_source_are_not_followed`, `test_a_link_in_the_guides_folder_is_replaced_not_written_through`, `test_a_file_too_big_for_a_guide_is_skipped`. |
| 6 | Low | **Two state files ignored the write rule.** The "I'm here" pins went through a fixed `<file>.tmp` and `guide-key.json` was opened in place, both following a link at that name, unlike every other write. | Both use `write_json` (a fresh temporary file renamed over). Test: `SavePin`. |
| 7 | Hardening | Prompts did not tell the agent that page text is data. | `prompts/guide/rules.md`: pages, excerpts and achievement text are material to quote, never instructions. No maker bump: the guide's shape and meaning are unchanged. |
| 8 | Hardening | CI ran third-party actions by mutable tag with the default token. | `permissions: contents: read`, `persist-credentials: false`, actions pinned to commits, a 15-minute timeout. |

### After 1.0.0: the marketplace review

The Omarchy plugin marketplace's maintainer review of 1.0.0 (commit
5a44ef9) reported two more; 1.0.1 fixes both, and the same pattern
wherever else it appeared. Its re-check of 1.0.1 confirmed both fixed and
found one more in that fix (11), fixed in 1.0.2.

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 9 | Medium | **A hand edit could truncate a file through a planted link.** `by_hand.update` opened `by-hand.json.lock` with `open(..., 'w')`, which follows a symlink and truncates. Another local user able to write in the data folder (a shared or loosely permissioned `XDG_DATA_HOME`) could point the lock at a file only the player can write and have the next tick empty it. The `.bad` copy of a broken file had the same flaw. | The lock is opened `O_RDWR\|O_CREAT\|O_NOFOLLOW\|O_CLOEXEC`, `0600`, no truncation, and refused unless `fstat` says a plain file of ours with one link. The data folder is created `0700`; a folder that is a link, not ours, or group/other-writable is refused with a `chmod go-w` hint (never changed on load). `.bad` goes through a temporary file and a rename. The same follow-a-link write was fixed in Steam's header miss marker (cache), `guide_bench.keep` and the saved platinum image. Tests: `tests/test_by_hand.py` `Unsafe`, `test_hand_says_what_to_fix_when_the_folder_is_unsafe`, `test_a_link_at_the_miss_marker_is_not_followed`, `test_a_link_at_out_is_replaced_not_written_through`. |
| 10 | Low (privacy) | **Notes passed in the command line.** The tracker ran `omatrophy.py hand note <store> <app> <api> <text>`, so a note sat in `/proc/<pid>/cmdline` while the command ran, readable by other local users. | The tracker runs `hand note ... --stdin` and writes the note to the process's stdin as one JSON-string line (Quickshell's `Process` can't close stdin, so one line, not EOF). The argument form stays for terminal use. Tests: `test_notes_go_on_stdin_never_in_the_command`, `test_hand_note_reads_one_json_line_from_stdin`, `test_stdin_note_refuses_what_is_not_one_json_string`. |
| 11 | Medium | **The saved image's mode was set by path.** Found by the same review at 1.0.1 (b3211b6), in 1.0.1's own fix: `share.place` closed its temporary image, then ran `os.chmod(tmp, 0o644)`. Saving into a folder another local user can write in (no sticky bit), they could swap the temporary name for a link to one of the player's files between the close and the chmod, making it world-readable. | The mode is set with `fchmod` on the open file before it closes; nothing is chmodded by path anywhere. Test: `test_a_swapped_temporary_file_never_gets_the_players_file_chmodded`. |

Docs that described the old behaviour were corrected: SECURITY.md (the
inbox forwards every card type in `cards.json`, not only unlock and
platinum; images; fetch limits; import), the README's network line (GOG's
icons and art come from GOG's image hosts), and `docs/specs/guides.md`.

## Checked, no change needed

- **Commands**: every process, in Python and QML, is an argument list,
  never a shell. `notify-send` gets `--` before text. The Guide key's
  Lua is built from a strictly parsed key or Hyprland's own answer,
  quoted with `json.dumps`; anything odd is a Lua error, not code. The
  Steam loader's Lua strings escape `\`, `"` and newlines.
- **Paths from data**: Steam, GOG and community ids are ASCII digits
  before they reach a path or URL; icon cache names are a URL's basename
  under a digit-checked folder; guide job files go through a character
  allowlist; `share` slugs names to `[a-z0-9-]`.
- **Watcher inbox** (`inbox.jsonl`): any of the user's processes may write
  it (the local user is trusted); lines are capped at 64 KB and must be a
  JSON object whose type has a card.
- **Store network**: HTTPS only, the stores' hosts only, redirects
  checked, 4 s socket timeout, 8 MB cap. Binary stats files are bounded.
  Comet's databases are opened read-only.
- **Agents**: Claude runs with no tools (or WebSearch and WebFetch for
  research), no MCP, no settings sources, `dontAsk`; unchecked agents
  never run; ai-jail options are an allowlist that cannot remove a fence.
  A model name is one argv element.
- **Platinum image**: a private temporary folder, paths into the generated
  QML go in as JSON string literals, art is local files only.
- **`dev/` scripts**: `mktemp -d` folders removed by a trap; the sandbox
  refuses to remove any other path.
- **Hygiene**: `tests/test_hygiene.py` passes with the private strings
  file present; no symlinks are tracked.

## Marketplace static scan

The marketplace's baseline (policy at f2732ad) over this branch: 39
files in scope, 0.96 MiB of text (limit 8 MiB), the largest
`TrackerView.qml` at 219 KiB (limit 512 KiB). Outcome **passed**: no
findings (`curl-pipe-shell`, `cargo-git-unpinned`,
`remote-git-execution-unpinned`, `sudoers-dangerous-passwordless-command`,
`privileged-process-control-from-shared-temp`) and no review capabilities
(installer, package-manager, privilege, remote-build, bundled binary,
service management, sudoers). The positive control (`curl ... | sh`,
`sudo systemctl`) came back `needs-fixes` with `installer`, `privilege` and
`service-management`, as it should. No tracked symlinks; `preview.png` is
3840 x 2160 (8.3 MP) and under 1 MB.

## Residual risks

- **Prompt injection** still steers what the agent writes. Every claim
  must quote a source OmaTrophy fetched, the agent has no file or shell
  tool, and links open only on a click and only for `https`, but a page
  can still make a guide wrong or point a link somewhere unhelpful. With
  web research on, the agent's own WebFetch can reach any URL a page
  names; it carries only the game's achievement list. ai-jail (`guide-jail
  on`) is the fence around the agent itself.
- **Through a proxy** (`https_proxy`), the guide fetch checks only the host
  name, not the address the proxy reaches.
- **The local user is trusted**: config, state, the inbox, IPC and the
  agent options can be changed by any process running as the user, which
  could do worse directly.
- **Images from the stores' CDNs** load in the panel when there is no
  cached copy, which tells Steam or GOG the panel opened (as the store's
  own client does).
- **The community backfill** (off by default) puts the SteamID64 in
  request URLs, as documented in ADR 11.
