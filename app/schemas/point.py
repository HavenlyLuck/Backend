from pydantic import BaseModel

class PointWalletResponse(BaseModel):
    woon_point: int
    ssal_point: int

    class Config:
        from_attributes = True
