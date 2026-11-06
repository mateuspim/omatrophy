#!/usr/bin/env python3
"""Check on a real run that an agent's guide adapter stays locked down
(ADR 14). The same as `omatrophy.py guide check`, kept for its name:

  dev/check-lock.py codex [model]
  dev/check-lock.py --jail claude [model]    inside ai-jail (guide-jail)

A pass without --jail is recorded for the agent binary installed now
(~/.local/state/omatrophy/guide-locks.json) and lets it make guides; an
update of the agent asks for the check again.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import omatrophy

args = sys.argv[1:]
jail = args[:1] == ['--jail']
args = args[1:] if jail else args
if not 1 <= len(args) <= 2:
    raise SystemExit(__doc__)
omatrophy.main(['omatrophy.py', 'guide', 'check', *args] + (['--jail'] if jail else []))
