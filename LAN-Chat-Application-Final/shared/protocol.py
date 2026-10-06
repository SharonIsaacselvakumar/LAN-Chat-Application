
import json

def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

def decode(line):
    return json.loads(line)
