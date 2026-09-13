from pydantic import BaseModel

class FontTransformRequest(BaseModel):
    text: str
    style: str

class FontTransformResponse(BaseModel):
    original_text: str
    transformed_text: str
    style: str

class FontStyleItem(BaseModel):
    id: str
    name: str
    preview: str
