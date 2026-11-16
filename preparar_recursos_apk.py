"""Run once on desktop before building. Adds packaged resource extensions only."""
from pathlib import Path
import re


def prepare(path=Path('buildozer.spec')):
    text=path.read_text(encoding='utf-8')
    pattern=r'(?m)^(source\.include_exts\s*=\s*)([^\n]*)$'
    match=re.search(pattern,text)
    if not match:raise RuntimeError('No existe source.include_exts en buildozer.spec; no se modificó el archivo.')
    values=[x.strip() for x in match.group(2).split(',') if x.strip()]
    for ext in ('py','png','jpg','ttf','wav','json','txt'):
        if ext not in values:values.append(ext)
    updated=text[:match.start(2)]+','.join(values)+text[match.end(2):]
    if updated!=text:
        backup=path.with_name('buildozer.spec.antes_menu')
        if not backup.exists():backup.write_text(text,encoding='utf-8')
        path.write_text(updated,encoding='utf-8')
    print('Extensiones comprobadas; versiones, requisitos y configuración Android conservados.')

if __name__=='__main__':prepare()
