from pydantic import BaseModel

class PrankTransformRequest(BaseModel):
    text: str
    effect: str

class PrankTransformResponse(BaseModel):
    original_text: str
    prank_text: str
    effect: str

class PrankEffectItem(BaseModel):
    id: str
    name: str
    description: str
