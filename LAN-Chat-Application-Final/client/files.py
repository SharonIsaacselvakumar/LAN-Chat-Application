
import base64
from pathlib import Path

def make_file_payload(path, receiver="*"):
    p = Path(path)
    return {
        "type":"file",
        "receiver":receiver,
        "filename":p.name,
        "data":base64.b64encode(p.read_bytes()).decode("ascii")
    }
