from pydantic import BaseModel

class RPTransformRequest(BaseModel):
    text: str
    style: str

class RPTransformResponse(BaseModel):
    original_text: str
    styled_text: str
    style: str

class RPStyleItem(BaseModel):
    id: str
    name: str
    sample: str
