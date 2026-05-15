import json
from graphify.detect import detect
from pathlib import Path
result = detect(Path('.'))
with open('.graphify_detect.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
files = result.get('files', {})
print('total_files:', result.get('total_files', 0))
print('total_words:', result.get('total_words', 0))
for k, v in files.items():
    if v:
        print(k + ': ' + str(len(v)) + ' files')
if result.get('warning'):
    print('WARNING:', result['warning'])
