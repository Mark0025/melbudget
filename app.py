import os
import json
import logging
import traceback
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from models import Transaction, TransactionSummary, MonthlyStats, DashboardData, TransactionType
from decimal import Decimal
from pathlib import Path
from utils.csv_processor import CSVProcessor

# Configure logging first
LOG_FOLDER = 'logs'
os.makedirs(LOG_FOLDER, exist_ok=True)

# Create logger
logger = logging.getLogger('budget_app')
logger.setLevel(logging.DEBUG)

# Create handlers
log_file = os.path.join(LOG_FOLDER, f'budget_app_{datetime.now().strftime("%Y%m%d")}.log')
file_handler = logging.FileHandler(log_file)
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Now try to import pandas
try:
    import pandas as pd
    logger.info('Successfully imported pandas')
except ImportError as e:
    logger.error(f'Failed to import pandas: {str(e)}')
    logger.error('Please install pandas using: pip install pandas')
    raise ImportError('Pandas is required. Please install it using: pip install pandas')

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configure upload settings first
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Then initialize the CSV processor with the configured upload folder
processor = CSVProcessor(Path(UPLOAD_FOLDER))

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    logger.info('Home page accessed')
    try:
        # Check for existing processed files
        processed_files = processor.get_processed_files()
        if processed_files:
            # Load the most recent file's data
            latest_file = processed_files[0]  # Changed from -1 since list is already sorted
            logger.info(f"Loading most recent file: {latest_file}")
            
            transactions = processor.load_all_transactions().get(latest_file, [])
            if transactions:
                # Calculate summary and monthly stats
                summary = TransactionSummary(
                    total_transactions=len(transactions),
                    total_spent=sum(t.amount for t in transactions if t.amount < 0),
                    total_received=sum(t.amount for t in transactions if t.amount > 0),
                    average_transaction=sum(t.amount for t in transactions) / len(transactions) if transactions else Decimal('0'),
                    date_range=(
                        f"{min(t.posting_date for t in transactions).strftime('%Y-%m-%d')} to "
                        f"{max(t.posting_date for t in transactions).strftime('%Y-%m-%d')}"
                    ) if transactions else "No date range available"
                )
                
                dashboard_data = DashboardData(
                    transactions=transactions,
                    summary=summary,
                    monthly_stats={}  # You can implement monthly stats calculation here
                )
                session['dashboard_data'] = dashboard_data.model_dump()
                return redirect(url_for('dashboard'))
            else:
                logger.warning(f"No transactions found in {latest_file}")
                
    except Exception as e:
        logger.error(f"Error processing CSV data: {e}")
        flash("Error processing transaction data", "error")
    
    return redirect(url_for('upload'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        logger.info('File upload attempt started')
        
        if 'file' not in request.files:
            logger.warning('No file part in the request')
            flash('No file selected')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            logger.warning('No file selected')
            flash('No file selected')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            logger.info(f'File uploaded successfully: {filename}')
            
            # Log file details
            file_size = os.path.getsize(filepath)
            logger.info(f'File size: {file_size} bytes')
            
            flash('File uploaded successfully')
            return redirect(url_for('map_headers', filename=filename))
        
        logger.error(f'Invalid file type: {file.filename}')
        flash('Invalid file type. Please upload a CSV file.')
        return redirect(request.url)
        
    return render_template('upload.html')

@app.route('/map-headers/<filename>', methods=['GET', 'POST'])
def map_headers(filename):
    logger.info(f'Header mapping started for file: {filename}')
    
    try:
        # Read CSV headers
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        df = pd.read_csv(filepath, nrows=0)  # Just read headers
        headers = df.columns.tolist()
        logger.info(f'CSV headers found: {headers}')
        
        # Define standard headers we expect
        standard_headers = [
            'Details', 'Posting Date', 'Description', 
            'Amount', 'Type', 'Balance', 'Check or Slip #'
        ]
        
        if request.method == 'POST':
            # Process the mapping and continue to CSV processing
            return redirect(url_for('process_csv', filename=filename))
            
        # Show mapping form
        return render_template('map_headers.html', 
                             filename=filename,
                             headers=headers,
                             standard_headers=standard_headers)
                             
    except Exception as e:
        logger.error(f'Error in header mapping: {str(e)}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        flash('Error processing CSV file')
        return redirect(url_for('upload'))

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f'Unhandled error: {str(error)}', exc_info=True)
    flash('An error occurred: ' + str(error))
    return redirect(url_for('upload'))

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f'Page not found: {request.url}')
    flash('Page not found')
    return redirect(url_for('upload'))

@app.route('/dashboard')
def dashboard():
    logger.info('Dashboard page accessed')
    
    if 'dashboard_data' not in session:
        logger.warning('No dashboard data in session')
        flash('No data to display. Please upload a CSV file first.')
        return redirect(url_for('upload'))
    
    try:
        # Get dashboard data from session
        dashboard_data = session['dashboard_data']
        
        # Convert back to proper types since session storage converts to basic types
        transactions = [Transaction(**t) for t in dashboard_data['transactions']]
        summary = TransactionSummary(**dashboard_data['summary'])
        monthly_stats = {
            k: MonthlyStats(**v) 
            for k, v in dashboard_data['monthly_stats'].items()
        }
        
        logger.info(f'Displaying {len(transactions)} transactions')
        
        return render_template('dashboard.html',
                             transactions=transactions,
                             summary=summary,
                             monthly_stats=monthly_stats)
                             
    except Exception as e:
        logger.error(f'Error displaying dashboard: {str(e)}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        flash('Error displaying dashboard')
        return redirect(url_for('upload'))

@app.route('/process-csv/<filename>')
def process_csv(filename):
    logger.info(f'Processing CSV file: {filename}')
    try:
        # Get file paths
        csv_file = Path(app.config['UPLOAD_FOLDER']) / filename
        
        # Process the CSV file
        df = pd.read_csv(csv_file)
        logger.info(f"Loaded CSV with {len(df)} rows")
        
        # Process transactions
        transactions = []
        for idx, row in df.iterrows():
            try:
                # Skip header row if present
                if row['Details'] == 'Details':
                    continue
                    
                # Get amount and balance
                amount = Decimal(str(row['Amount']).replace('$', '').replace(',', ''))
                balance = Decimal(str(row['Balance']).replace('$', '').replace(',', ''))
                
                # Parse date
                posting_date = datetime.strptime(str(row['Posting Date']), '%m/%d/%Y')
                
                # Determine transaction type
                details = str(row['Details']).upper()
                type_str = str(row['Type']).upper()
                
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
            logger.error('No transactions were processed')
            flash('No transactions could be processed from the file')
            return redirect(url_for('upload'))
            
        # Calculate summary
        summary = TransactionSummary(
            total_transactions=len(transactions),
            total_spent=sum(t.amount for t in transactions if t.amount < 0),
            total_received=sum(t.amount for t in transactions if t.amount > 0),
            average_transaction=sum(t.amount for t in transactions) / len(transactions),
            date_range=(
                f"{min(t.posting_date for t in transactions).strftime('%Y-%m-%d')} to "
                f"{max(t.posting_date for t in transactions).strftime('%Y-%m-%d')}"
            )
        )
        
        # Calculate monthly stats
        monthly_stats = {}
        
        # Store in session
        dashboard_data = DashboardData(
            transactions=transactions,
            summary=summary,
            monthly_stats=monthly_stats
        )
        session['dashboard_data'] = dashboard_data.model_dump()
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logger.error(f'Error processing CSV: {str(e)}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        flash('Error processing CSV file')
        return redirect(url_for('upload'))

if __name__ == '__main__':
    logger.info('Application started')
    app.run(debug=True)