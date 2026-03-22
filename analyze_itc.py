"""Quick analyzer for ITC Report 2025"""
import sys
sys.path.insert(0, r'e:\NVidia api')

from FinancialAnalyzer import FinancialAnalyzer

# Load the ITC report
analyzer = FinancialAnalyzer(r'e:\NVidia api\ITC-Report-and-Accounts-2025.pdf')
analyzer.load()

print("\n" + "="*70)
print("ITC Report 2025 - Ready for queries!")
print("="*70)

# Run some sample queries
sample_queries = [
    "What is the total revenue for 2025?",
    "What is the net profit?",
    "What are the segment revenues?",
]

for query in sample_queries:
    answer = analyzer.query(query)
    print(answer)

# Interactive mode
print("\nReady for your queries! (type 'exit' to quit)")
while True:
    try:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        if not user_input:
            continue
        answer = analyzer.query(user_input)
        print(answer)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        break
    except Exception as e:
        print(f"Error: {str(e)}")
