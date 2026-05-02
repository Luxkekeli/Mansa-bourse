import json
p = json.load(open(r'D:\KLAUD\Claude_KI\brvm_data\progress.json'))
done = [k for k in p if k.startswith('DONE_')]
mdata = [k for k in p if not k.startswith('DONE_') and p[k] > 0]
print(f'Tickers completed: {len(done)}/58')
print(f'Months with data: {len(mdata)}')
total = sum(p[k] for k in done)
print(f'Total rows so far: {total}')
print()
for k in sorted(done):
    print(f'  {k[5:]:20s} {p[k]:>6} rows')
