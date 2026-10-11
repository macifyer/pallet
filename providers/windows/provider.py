#!/usr/bin/env python3
"""Search and control live Hyprland windows."""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
MAX_RESULTS = 15
ADDRESS = re.compile(r"^0x[0-9a-fA-F]+$")
XDG_APPS_DIRS = [Path.home()/".local/share/applications", Path.home()/".local/share/flatpak/exports/share/applications", Path("/usr/local/share/applications"), Path("/usr/share/applications"), Path("/var/lib/flatpak/exports/share/applications")]
_icons: dict[str, str] = {}
def load_icon_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for directory in XDG_APPS_DIRS:
        if not directory.is_dir(): continue
        for desktop in sorted(directory.glob("*.desktop")):
            try: text = desktop.read_text(encoding="utf-8", errors="replace")
            except OSError: continue
            fields: dict[str, str] = {}; in_entry = False
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("[") and line.endswith("]"): in_entry = line == "[Desktop Entry]"; continue
                if in_entry and "=" in line:
                    key, _, value = line.partition("="); fields.setdefault(key, value)
            icon = fields.get("Icon", "").strip()
            if not icon: continue
            keys = {desktop.name.removesuffix(".desktop").lower()}
            for key in ("StartupWMClass", "Name"):
                if fields.get(key, "").strip(): keys.add(fields[key].strip().lower())
            exec_line = fields.get("Exec", "").split()
            if exec_line and Path(exec_line[0]).name.lower() not in ("env", "flatpak", "sh", "bash"): keys.add(Path(exec_line[0]).name.lower())
            for key in keys: mapping.setdefault(key, icon)
    return mapping
def hyprctl_json(*args: str) -> Any:
    try: return json.loads(subprocess.run(["hyprctl", *args, "-j"], check=False, capture_output=True, text=True, timeout=2).stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired): return None
def eval_dispatch(builder: str) -> bool:
    try:
        result = subprocess.run(["hyprctl", "dispatch", builder], check=False, capture_output=True, text=True, timeout=2)
        return result.returncode == 0 and result.stdout.strip().startswith("ok")
    except (OSError, subprocess.TimeoutExpired): return False
def clients() -> list[dict]:
    value = hyprctl_json("clients"); return value if isinstance(value, list) else []
def active_address() -> str:
    value = hyprctl_json("activewindow"); return str(value.get("address", "")) if isinstance(value, dict) else ""
def workspace_label(client: dict) -> str:
    workspace = client.get("workspace") or {}
    if not isinstance(workspace, dict): return "workspace ?"
    name = str(workspace.get("name", "")).strip(); return name if name else "workspace " + str(workspace.get("id", "?"))
def icon_candidates(client: dict) -> list[str]:
    seen: set[str] = set(); out: list[str] = []
    for token in (client.get("class"), client.get("initialClass")):
        low = str(token or "").strip().lower()
        for name in (_icons.get(low, ""), low):
            if name and name not in seen: seen.add(name); out.append(name)
    for name in ("applications-other", "application-x-executable"):
        if name not in seen: out.append(name)
    return out
def visible_client(client: dict) -> bool:
    return bool(ADDRESS.fullmatch(str(client.get("address", "")))) and bool(client.get("mapped", True)) and not bool(client.get("hidden", False))
def score(query: str, client: dict, active: str) -> float:
    title = str(client.get("title", "")).lower(); klass = str(client.get("class", "")).lower(); initial = str(client.get("initialClass", "")).lower(); workspace = workspace_label(client).lower()
    if title.startswith(query) or klass.startswith(query) or initial.startswith(query): base = .94
    elif any(word.startswith(query) for word in title.split()) or any(word.startswith(query) for word in klass.split()): base = .86
    elif query in title or query in klass or query in initial: base = .74
    elif query in workspace: base = .55
    else: return 0.0
    return min(1.0, base + .05) if str(client.get("address")) == active else base
def result_for(client: dict, rank: float) -> dict:
    address = str(client["address"]); title = str(client.get("title") or client.get("class") or "Untitled window"); klass = str(client.get("class") or client.get("initialClass") or "Unknown app"); icons = icon_candidates(client); state = [workspace_label(client), klass]
    if client.get("floating"): state.append("floating")
    if client.get("fullscreen"): state.append("fullscreen")
    return {"id":"windows:"+address,"title":title,"subtitle":" · ".join(state),"icon":icons[0],"icons":icons[1:],"fallbackIcon":"▣","keywords":" ".join([klass,str(client.get("initialClass") or ""),workspace_label(client)]).lower(),"score":rank,"provider":"windows","actions":[{"type":"custom","kind":"focus-window","title":"Focus window","address":address},{"type":"custom","kind":"close-window","title":"Close window","address":address},{"type":"custom","kind":"toggle-floating","title":"Toggle floating","address":address},{"type":"custom","kind":"toggle-fullscreen","title":"Toggle fullscreen","address":address},{"type":"copy","title":"Copy title","text":title}]}
def resolve_live(address: object) -> bool: return isinstance(address, str) and bool(ADDRESS.fullmatch(address)) and any(str(c.get("address")) == address for c in clients())
def execute(action: dict) -> bool:
    address = action.get("address")
    if not resolve_live(address): return False
    selector = f'window = "address:{address}"'; kind = action.get("kind")
    if kind == "focus-window": return eval_dispatch(f"hl.dsp.focus({{ {selector} }})")
    if kind == "close-window": return eval_dispatch(f"hl.dsp.window.close({{ {selector} }})")
    if kind == "toggle-floating": return eval_dispatch(f'hl.dsp.window.float({{ action = "toggle", {selector} }})')
    if kind == "toggle-fullscreen": return eval_dispatch(f'hl.dsp.window.fullscreen({{ mode = "fullscreen", action = "toggle", {selector} }})')
    return False
def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q: return []
    active = active_address(); ranked = [(score(q,c,active),c) for c in clients() if visible_client(c)]; ranked = [(r,c) for r,c in ranked if r > 0]; ranked.sort(key=lambda pair:pair[0],reverse=True); return [result_for(c,r) for r,c in ranked[:MAX_RESULTS]]
def main() -> None:
    global _icons; _icons = load_icon_map()
    for line in sys.stdin:
        try: msg=json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search": print(json.dumps({"id":msg.get("id",""),"results":search(str(msg.get("query","")))}),flush=True)
        elif msg.get("op") == "execute": print(json.dumps({"id":msg.get("id",""),"executed":execute(msg["action"]) if isinstance(msg.get("action"),dict) else False}),flush=True)
        elif msg.get("op") == "cancel": print(json.dumps({"id":msg.get("target",""),"cancelled":True}),flush=True)
if __name__ == "__main__": main()
