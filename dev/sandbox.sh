#!/usr/bin/env bash
# Run one command against throwaway data folders, e.g. to try the CLI by hand:
#   dev/sandbox.sh python3 omatrophy.py status
#   dev/sandbox.sh --home bash -c 'python3 omatrophy.py set sound off && python3 omatrophy.py now'
#   --home also fakes HOME: state, cache and config are ~-relative, so only
#          then do writes stay out of the real home (real launchers are then
#          not found either)
#
# Why this exists: an agent once ran `export XDG_DATA_HOME=$(mktemp -d)` in one
# shell call and `rm -rf "$XDG_DATA_HOME"` in the next. Each call is a fresh
# shell, so the variable had reverted to the real ~/.local/share and the
# cleanup wiped it. Here the folder lives and dies inside one process, and the
# cleanup refuses any path that is not the one mktemp made.
set -euo pipefail

fake_home=0
if [[ ${1:-} == --home ]]; then fake_home=1; shift; fi
(( $# )) || { sed -n '2,7p' "$0" >&2; exit 2; }

tmp_root=${TMPDIR:-/tmp}
dir=$(mktemp -d "$tmp_root/omatrophy-sandbox.XXXXXXXX")

cleanup() {
  # Only ever remove the exact folder made above; anything else is a bug.
  case $dir in
    "$tmp_root"/omatrophy-sandbox.????????) rm -rf -- "$dir" ;;
    *) echo "sandbox: refusing to remove unexpected path '$dir'" >&2 ;;
  esac
}
trap cleanup EXIT

mkdir -p "$dir"/{data,config,state,cache}
export XDG_DATA_HOME="$dir/data" XDG_CONFIG_HOME="$dir/config"
export XDG_STATE_HOME="$dir/state" XDG_CACHE_HOME="$dir/cache"
if (( fake_home )); then
  mkdir -p "$dir/home"
  export HOME="$dir/home"
fi
export OMATROPHY_SANDBOX="$dir"

# Not exec: the trap must run after the command exits.
"$@"
