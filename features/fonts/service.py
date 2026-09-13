from features.fonts.transforms import transform_text, FONTS_MAP

class FontsService:
    def get_available_styles(self) -> list[dict]:
        styles = []
        for key in FONTS_MAP.keys():
            styles.append({
                "id": key,
                "name": key.replace("_", " ").title(),
                "preview": transform_text("Preview 123", key)
            })
        return styles

    def transform(self, text: str, style: str) -> str:
        return transform_text(text, style)

fonts_service = FontsService()
