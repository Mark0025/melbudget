from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field

class TransactionType(str, Enum):
    DEBIT_CARD = "DEBIT_CARD"
    ACH_CREDIT = "ACH_CREDIT"
    ACH_DEBIT = "ACH_DEBIT"
    FEE_TRANSACTION = "FEE_TRANSACTION"
    CHECK_DEPOSIT = "CHECK_DEPOSIT"
    MISC_DEBIT = "MISC_DEBIT"
    DEPOSIT = "DEPOSIT"

class Transaction(BaseModel):
    details: str = Field(..., description="Transaction type (DEBIT/CREDIT)")
    posting_date: datetime = Field(..., description="Transaction date")
    description: str = Field(..., description="Transaction description")
    amount: Decimal = Field(..., description="Transaction amount")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    balance: Decimal = Field(..., description="Running balance")
    check_number: Optional[str] = Field(None, description="Check or slip number")

class TransactionSummary(BaseModel):
    total_transactions: int = Field(..., description="Total number of transactions")
    total_spent: Decimal = Field(..., description="Total amount spent")
    total_received: Decimal = Field(..., description="Total amount received")
    average_transaction: Decimal = Field(..., description="Average transaction amount")
    date_range: str = Field(..., description="Date range of transactions")

class MonthlyStats(BaseModel):
    total_spent: Decimal = Field(..., description="Total spent in month")
    total_received: Decimal = Field(..., description="Total received in month")
    transaction_count: int = Field(..., description="Number of transactions")
    largest_transaction: Decimal = Field(..., description="Largest transaction amount")
    most_common_type: str = Field(..., description="Most common transaction type")

class DashboardData(BaseModel):
    transactions: List[Transaction] = Field(..., description="List of transactions")
    summary: TransactionSummary = Field(..., description="Transaction summary statistics")
    monthly_stats: Dict[str, MonthlyStats] = Field(..., description="Monthly statistics")

class CSVMapping(BaseModel):
    file_pattern: str = Field(..., description="Pattern to match CSV filename")
    column_mappings: dict[str, str] = Field(..., description="Maps CSV headers to standard fields")
    date_format: str = Field("%m/%d/%Y", description="Format for parsing dates")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_pattern": "Chase*Activity*.CSV",
                "column_mappings": {
                    "Details": "details",
                    "Posting Date": "posting_date",
                    "Description": "description",
                    "Amount": "amount",
                    "Type": "transaction_type",
                    "Balance": "balance",
                    "Check or Slip #": "check_number"
                },
                "date_format": "%m/%d/%Y"
            }
        }