import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from decimal import Decimal, InvalidOperation
from pathlib import Path
import logging
from typing import List, Dict

from models import Transaction, TransactionType

logger = logging.getLogger('budget_app')

class CSVProcessor:
    def __init__(self, mapping_dir: Path = Path("uploads")):
        self.mapping_dir = mapping_dir
        self.mapping_dir.mkdir(exist_ok=True)
        self._cached_data: Dict[str, List[Transaction]] = {}

    def get_processed_files(self) -> List[str]:
        """Get list of all processed CSV files"""
        csv_files = list(self.mapping_dir.glob('*.CSV'))
        csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return [f.name for f in csv_files]

    def load_all_transactions(self) -> Dict[str, List[Transaction]]:
        """Load all processed transactions from all files"""
        if not self._cached_data:
            for file_name in self.get_processed_files():
                csv_path = self.mapping_dir / file_name
                if csv_path.exists():
                    self._cached_data[file_name] = self.process_csv(csv_path)
        return self._cached_data

    def clean_decimal(self, value: str) -> Decimal:
        """Clean and convert string to Decimal"""
        try:
            # Remove currency symbols, spaces, and commas
            cleaned = str(value).replace('$', '').replace(',', '').strip()
            # Handle parentheses for negative numbers
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = '-' + cleaned[1:-1]
            return Decimal(cleaned)
        except (InvalidOperation, TypeError):
            return Decimal('0')

    def process_csv(self, csv_path: Path) -> List[Transaction]:
        try:
            logger.info(f"Processing CSV file: {csv_path}")
            
            # Read CSV with explicit headers
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded CSV with {len(df)} rows")
            
            # Verify expected columns exist
            expected_columns = ['Details', 'Posting Date', 'Description', 'Amount', 'Type', 'Balance', 'Check or Slip #']
            if not all(col in df.columns for col in expected_columns):
                logger.error(f"Missing expected columns. Found: {df.columns}")
                return []
            
            transactions = []
            for idx, row in df.iterrows():
                try:
                    # Clean and convert amount
                    # Clean and convert amount
                    amount = self.clean_decimal(row['Amount'])
                    
                    # Clean and convert balance 
                    balance = self.clean_decimal(row['Balance'])
                    
                    # Parse date with flexible format
                    try:
                        # First try standard format
                        posting_date = datetime.strptime(str(row['Posting Date']), '%m/%d/%Y')
                    except ValueError:
                        try:
                            # Fall back to dateutil parser
                            posting_date = date_parser.parse(str(row['Posting Date']))
                        except Exception as e:
                            logger.error(f"Failed to parse date '{row['Posting Date']}': {e}")
                            # Use today's date as fallback
                            posting_date = datetime.now()
                    
                    # Get transaction type
                    details = str(row['Details']).upper()
                    type_str = str(row['Type']).upper()
                    
                    # Map transaction types
                    if 'CREDIT' in details or 'ACH_CREDIT' in type_str:
                        trans_type = TransactionType.ACH_CREDIT
                    elif 'DSLIP' in details or 'CHECK' in type_str:
                        trans_type = TransactionType.CHECK_DEPOSIT
                    elif 'FEE' in type_str:
                        trans_type = TransactionType.FEE_TRANSACTION
                    elif 'ACH_DEBIT' in type_str:
                        trans_type = TransactionType.ACH_DEBIT
                    elif 'DEBIT_CARD' in type_str:
                        trans_type = TransactionType.DEBIT_CARD
                    elif 'DEPOSIT' in type_str:
                        trans_type = TransactionType.DEPOSIT
                    else:
                        trans_type = TransactionType.MISC_DEBIT
                    
                    transaction = Transaction(
                        details=details,
                        posting_date=posting_date,
                        description=str(row['Description']).strip(),
                        amount=amount,
                        transaction_type=trans_type,
                        balance=balance,
                        check_number=str(row['Check or Slip #']) if pd.notna(row['Check or Slip #']) else None
                    )
                    transactions.append(transaction)
                    
                except Exception as e:
                    logger.error(f"Error processing row {idx}: {row.to_dict()}")
                    logger.error(f"Error details: {str(e)}")
                    continue

            if not transactions:
                logger.warning("No transactions were processed")
            else:
                logger.info(f"Successfully processed {len(transactions)} transactions")
                
            return transactions
            
        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            return []
