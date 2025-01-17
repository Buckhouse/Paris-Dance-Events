from datetime import datetime
import locale

# Set French locale
locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')

# Test different format codes
format_tests = {
    '%b': 'Abbreviated month name',
    '%B': 'Full month name',
    '%d': 'Day of month as number (01-31)',
    '%-d': 'Day of month as number (1-31, no leading zero)',
    '%m': 'Month as number (01-12)',
    '%Y': 'Year with century'
}

print("French locale date format tests for all months:")
print("-" * 70)
print(f"{'Month':6} | {'%b':8} | {'%B':12} | Description")
print("-" * 70)

# Test each month
for month in range(1, 13):
    date = datetime(2024, month, 15)
    print(f"{month:2d}     | {date.strftime('%b'):8} | {date.strftime('%B'):12} | {format_tests['%b']}")

print("-" * 70)