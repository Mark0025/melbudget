# Budget App Documentation

## Overview
A Flask-based budget tracking application that processes Chase bank CSV statements and provides transaction analysis.

## Data Flow
1. CSV Upload
   - User uploads Chase bank statement CSV
   - File saved to `uploads/` directory
   - Filename format: `Chase3619_Activity_YYYYMMDD.CSV`

2. Data Processing
   - CSV processed into standardized JSON format
   - Data structure matches template in `uploads/chase.json`
   - Fields converted to appropriate types:
     ```json
     {
       "Details": "DEBIT|CREDIT|DSLIP",
       "Posting Date": "MM/DD/YYYY",
       "Description": "string",
       "Amount": float,
       "Type": "DEBIT_CARD|ACH_CREDIT|etc",
       "Balance": float,
       "Check or Slip #": string|null
     }
     ```

3. Transaction Model
   - CSV data converted to Transaction objects
   - Handles validation and type conversion
   - Stores in session for dashboard display

## Error Handling
- Invalid CSV format: Redirects to upload page
- Data conversion errors: Logs error, continues processing
- Missing fields: Sets defaults or nulls
- Invalid types: Attempts conversion or skips record

## File Structure 