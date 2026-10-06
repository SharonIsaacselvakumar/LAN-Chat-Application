
class ChatStore:
    def __init__(self):
        self.items = []

    def add(self, kind, sender, text, timestamp, receiver="*"):
        self.items.append({
            "kind":kind, "sender":sender, "text":text,
            "timestamp":timestamp, "receiver":receiver
        })
