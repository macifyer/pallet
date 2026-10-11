# files provider

Searches files and directories under `$HOME`.

## Index

Built once at provider start with `fd` when installed, otherwise `os.walk`
with the same prune list (`.git`, `node_modules`, `__pycache__`, caches,
package registries, Trash). Refreshed lazily after 60 s. Capped at 60k
entries; the provider requires at least three query characters before it
answers, so home-listing noise never floods a one-letter search.

## Ranking

Basename prefix > word prefix > substring; directories lose ties with
their files; files touched in the last 7 days get a small recency nudge;
deep paths are penalized slightly. Final order still belongs to the
frontend fuzzy pass.

## Actions

| Result | Actions |
|---|---|
| File | Open (xdg-open) · Open containing folder · Open terminal here · Copy path |
| Directory | Open (file manager) · Open terminal here · Copy path |

"Open terminal here" launches `foot --working-directory <dir>` as raw argv.
