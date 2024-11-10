import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from decimal import Decimal, InvalidOperation
from pathlib import Path
import logging
from typing import List, Dict
import csv
import json

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
            if pd.isna(value) or not value:
                return Decimal('0')
            
            # Convert to string and clean
            cleaned = str(value).replace('$', '').replace(',', '').strip()
            
            # Handle parentheses for negative numbers
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = '-' + cleaned[1:-1]
                
            # Remove any trailing spaces or characters
            cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
            
            # Convert to Decimal
            decimal_value = Decimal(cleaned)
            
            logger.debug(f"Cleaned decimal: {value} -> {decimal_value}")
            return decimal_value
            
        except (InvalidOperation, TypeError) as e:
            logger.error(f"Error converting {value} to Decimal: {e}")
            return Decimal('0')

    def process_csv_row(self, row):
        """Process a single CSV row with proper type conversion"""
        try:
            processed = {}
            
            # Details field (str: "DEBIT" | "CREDIT" | "DSLIP")
            processed["Details"] = str(row.get("Details", "")).strip()
            
            # Posting Date (str in format MM/DD/YYYY)
            date_str = row.get("Posting Date", "").strip()
            processed["Posting Date"] = date_str
            
            # Description (str) - Handle quotes and extra spaces
            desc = row.get("Description", "").strip()
            if desc.startswith('"') and desc.endswith('"'):
                desc = desc[1:-1]
            processed["Description"] = desc
            
            # Amount (float) - Handle negative values and currency formatting
            amount_str = str(row.get("Amount", "0")).strip()
            try:
                # Remove any currency symbols and commas
                amount_str = amount_str.replace("$", "").replace(",", "")
                processed["Amount"] = float(amount_str)
            except ValueError:
                processed["Amount"] = 0.0
            
            # Map CSV transaction types to our enum values
            type_mapping = {
                'ATM': 'MISC_DEBIT',  # Map ATM transactions to MISC_DEBIT
                'DEBIT_CARD': 'DEBIT_CARD',
                'ACH_CREDIT': 'ACH_CREDIT',
                'ACH_DEBIT': 'ACH_DEBIT',
                'FEE_TRANSACTION': 'FEE_TRANSACTION',
                'CHECK_DEPOSIT': 'CHECK_DEPOSIT',
                'DEPOSIT': 'DEPOSIT',
                'MISC_DEBIT': 'MISC_DEBIT'
            }
            
            raw_type = str(row.get("Type", "")).strip()
            processed["Type"] = type_mapping.get(raw_type, 'MISC_DEBIT')  # Default to MISC_DEBIT if unknown
            
            # Balance (float) - Handle currency formatting
            balance_str = str(row.get("Balance", "0")).strip()
            try:
                balance_str = balance_str.replace("$", "").replace(",", "")
                processed["Balance"] = float(balance_str)
            except ValueError:
                processed["Balance"] = 0.0
            
            # Check or Slip # (str or null) - Keep as string, don't convert to int
            check_num = row.get("Check or Slip #", "").strip()
            if check_num and check_num != "," and check_num != ",,":
                processed["Check or Slip #"] = str(check_num)  # Keep as string
            else:
                processed["Check or Slip #"] = None
                
            return processed
            
        except Exception as e:
            logger.error(f"Error processing row: {row} - Error: {e}")
            return None

    def process_csv(self, csv_file_path):
        """Process the CSV file and return structured Transaction objects"""
        with open(csv_file_path, 'r') as file:
            csv_reader = csv.DictReader(file)
            
            transactions = []
            for row in csv_reader:
                processed_row = self.process_csv_row(row)
                if processed_row:
                    # Fix: Change 'type' to 'transaction_type' to match model
                    transaction = Transaction(
                        details=processed_row["Details"],
                        posting_date=datetime.strptime(processed_row["Posting Date"], "%m/%d/%Y"),
                        description=processed_row["Description"],
                        amount=Decimal(str(processed_row["Amount"])),
                        transaction_type=processed_row["Type"],
                        balance=Decimal(str(processed_row["Balance"])),
                        check_number=processed_row["Check or Slip #"]
                    )
                    transactions.append(transaction)
            
            return transactions

    def save_json(self, data, output_path):
        """Save the processed data as JSON without comments"""
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
