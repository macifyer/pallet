import json
import sys


def search(query: str) -> list[dict]:
    return [
        {
            "id": "template.hello",
            "title": f"Hello: {query}",
            "subtitle": "Template provider",
            "icon": "text-x-script",
            "score": 0.1,
            "actions": [{"type": "copy", "text": query}],
        }
    ]


def main() -> None:
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("op") == "search":
            print(json.dumps({"id": msg["id"], "results": search(msg.get("query", ""))}), flush=True)
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target"), "cancelled": True}), flush=True)


if __name__ == "__main__":
    main()
