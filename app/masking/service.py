class MaskService:
    def mask(self, text: str, entities: list) -> str:
        if not entities:
            return text

        # sort theo start giảm dần
        entities_sorted = sorted(entities, key=lambda e: e.start, reverse=True)

        masked = text

        for e in entities_sorted:
            label = f"[{e.type}]"
            masked = masked[: e.start] + label + masked[e.end :]

        return masked