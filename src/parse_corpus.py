"""Parse KIOM Donguibogam volume txts into structured passage units.
Each line is: <2-char tag>\t<content>. Hierarchy tags: AA=chapter(편/권),
BB=section(門), CC=subcategory(목). Content tags carry body/prescription/acupoint text.
"""
import os, re, glob, json, sys

HIER = {'AA':'chapter','BB':'section','CC':'subcategory'}
# content-bearing tags (body text, prescription names/contents, acupoints)
CONTENT = {'ZZ','SS','DP','DD','EP','DH','CH','DK','CP','EE'}
SKIP = {'XX','OO','Z2','TT','PP','BB2'}  # metadata / TOC

def parse_file(path):
    chapter=section=subcat=None
    units=[]
    for raw in open(path, encoding='utf-8'):
        if raw.startswith('//') or not raw.strip():
            continue
        parts = raw.rstrip('\n').split('\t', 1)
        if len(parts)!=2:
            continue
        tag, text = parts[0].strip(), parts[1].strip()
        if tag=='AA': chapter=text; section=subcat=None; continue
        if tag=='BB': section=text; subcat=None; continue
        if tag=='CC': subcat=text; continue
        if tag in CONTENT:
            units.append({'chapter':chapter,'section':section,'subcategory':subcat,
                          'tag':tag,'text':text,'source':os.path.basename(path)})
    return units

def main(data_dir):
    files = sorted(glob.glob(os.path.join(data_dir,'동의보감_*.txt')))
    all_units=[]
    for f in files:
        all_units += parse_file(f)
    # tag counts
    from collections import Counter
    tc=Counter(u['tag'] for u in all_units)
    print('files:',len(files))
    print('TOTAL content units (all content tags):', len(all_units))
    print('  ZZ only (body):', tc['ZZ'])
    print('  ZZ+SS+DP:', tc['ZZ']+tc['SS']+tc['DP'])
    print('  tag breakdown:', dict(tc))
    # grouped: DP + trailing SS/DD merged into one prescription unit
    grouped=[]
    i=0
    for u in all_units:
        if u['tag']=='DP':
            grouped.append(u)  # herb/prescription head
        elif u['tag'] in {'SS','DD','DH','DK','EP','CH','CP','EE'} and grouped and grouped[-1]['tag'] in {'DP','__merged'}:
            g=grouped[-1]; g['text']=g['text']+' '+u['text']; g['tag']='__merged'
        else:
            grouped.append(u)
    print('  grouped (DP+SS merged):', len(grouped))
    json.dump(all_units, open('results/passages.json','w'), ensure_ascii=False)
    return all_units

if __name__=='__main__':
    dd = sys.argv[1] if len(sys.argv)>1 else '/sessions/sweet-wonderful-mayer/mnt/새 폴더'
    main(dd)
