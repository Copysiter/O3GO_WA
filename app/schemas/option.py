from pydantic import BaseModel


class OptionStr(BaseModel):
    text: str
    value: str

class OptionInt(BaseModel):
    text: str
    value: int

class OptionBool(BaseModel):
    text: str
    value: bool