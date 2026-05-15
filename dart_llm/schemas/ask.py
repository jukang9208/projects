from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    context: str = ""       
    max_tokens: int = 512
    temperature: float = 0.3


class AskResponse(BaseModel):
    answer: str
    question: str
