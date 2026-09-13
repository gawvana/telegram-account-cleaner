from features.rp.styles import transform_text, RP_STYLES_MAP

class RPService:
    def get_styles(self) -> list[dict]:
        return [
            {"id": key, "name": val["name"], "sample": val["sample"]}
            for key, val in RP_STYLES_MAP.items()
        ]

    def transform(self, text: str, style: str) -> str:
        return transform_text(text, style)

rp_service = RPService()
