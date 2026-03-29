import json
import glob
import os

files = glob.glob('test_results/full_*_20260329*.json')
out = []

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        data = json.load(file)
        times = [x['time'] for x in data]
        if times:
            avg = sum(times)/len(times)
            fast = sum(1 for t in times if t < 1)
            slow = sum(1 for t in times if t > 5)
            # count correct formatting/hallucinations by heuristics maybe
            out.append(f'{os.path.basename(f)}: Avg {avg:.2f}s, Fast: {fast}, Slow (>5s): {slow}, Max: {max(times):.2f}s, Total: {len(times)}')

with open('test_results/summary.txt', 'w') as fh:
    fh.write('\n'.join(out))
