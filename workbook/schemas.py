from ninja import Schema
from datetime import date
from typing import Optional

class WorkbookCreateSchema(Schema):
    title: str = "My Workbook",
    opening_balance: float

class TransactionCreateSchema(Schema):
    category: str
    amount: int
    remarks: Optional[str] = None
    nature: str
    date: date

class TransactionUpdateSchema(Schema):
    # All fields are optional so the user can update just one field if they want (like a PATCH request)
    category: Optional[str] = None
    amount: Optional[int] = None
    remarks: Optional[str] = None
    nature: Optional[str] = None
    date: Optional[date] = None

class GetWorkbookTransactionsSchema(Schema):
    workbook_id: int
class WorkbookUpdateSchema(Schema):
    title: str = "My Workbook",
    opening_balance: float = 0