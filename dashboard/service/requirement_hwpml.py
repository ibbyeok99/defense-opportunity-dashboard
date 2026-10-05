"""HWPML 본문만 읽는다. 외부 DTD·임의 엔티티·내장 프로그램은 처리하지 않는다."""
import re
from xml.etree import ElementTree as ET

MAX_XML=8*1024*1024
MAX_TEXT=2_000_000
MAX_NODES=50_000
MAX_DEPTH=64
# 실제 계약 조건 XML3개의 고정 nbsp 선언만 문자 참조로 바꾼다. 엔티티 확장은 하지 않는다.
NBSP_DOCTYPE=re.compile(r'<!DOCTYPE\s+HWPML\s*\[\s*<!ENTITY\s+nbsp\s+(?P<quote>[\"\x27])&#160;(?P=quote)\s*>\s*\]\s*>')
OBJECTS={'PICTURE','OLEOBJECT','EQUATION','DRAWING','VIDEO','AUDIO','SCRIPT','MACRO'}


def hwpml_sections(blob):
    if len(blob)>MAX_XML:
        raise ValueError('HWPML 본문 크기 한도를 초과했습니다.')
    text=blob.decode('utf-8-sig',errors='strict')
    declaration=re.search(r'<!DOCTYPE\b',text,re.I)
    if declaration:
        match=NBSP_DOCTYPE.match(text,declaration.start())
        if not match:
            raise ValueError('HWPML 임의 DTD·엔티티 선언은 처리하지 않습니다.')
        text=text[:match.start()]+text[match.end():]
        text=text.replace('&nbsp;','&#160;')
    if re.search(r'<!DOCTYPE\b|<!ENTITY\b',text,re.I):
        raise ValueError('HWPML 임의 DTD·엔티티 선언은 처리하지 않습니다.')
    try:
        root=ET.fromstring(text)
    except ET.ParseError:
        raise ValueError('손상된 HWPML 본문입니다.') from None
    if root.tag!='HWPML' or root.get('Version')!='2.1':
        raise ValueError('지원하지 않는 HWPML 버전·본문 구조입니다.')
    stack=[(root,0)]
    count=0
    while stack:
        node,depth=stack.pop()
        count+=1
        if count>MAX_NODES or depth>MAX_DEPTH:
            raise ValueError('HWPML 노드·깊이 한도를 초과했습니다.')
        stack.extend((child,depth+1) for child in node)
    body=root.find('BODY')
    if body is None:
        raise ValueError('손상된 HWPML 본문 구역입니다.')
    sections=[]
    total=0

    def paragraph(node):
        parts=[]
        def visit(child,initial=False):
            if child.tag in {'SCRIPT','MACRO'} or (child.tag=='P' and not initial):
                return
            if child.tag=='CHAR':
                parts.append(''.join(child.itertext()))
            elif child.tag=='TAB':
                parts.append(' ')
            elif child.tag in {'LINEBREAK','BR'}:
                parts.append('\n')
            else:
                for value in child:
                    visit(value)
        visit(node,True)
        return ''.join(parts)

    for index,section in enumerate(body.findall('SECTION'),1):
        nodes=[section]
        paragraphs=[]
        while nodes:
            node=nodes.pop()
            if node.tag in {'SCRIPT','MACRO'}:
                continue
            if node.tag=='P':
                paragraphs.append(paragraph(node))
            nodes.extend(reversed(list(node)))
        content='\n'.join(p for p in paragraphs if p.strip())
        total+=len(content)
        if total>MAX_TEXT:
            raise ValueError('HWPML 전체 텍스트 한도를 초과했습니다.')
        sections.append((f'HWPML 구역 {index}',content))
        found={node.tag for node in section.iter() if node.tag in OBJECTS}
        if found:
            sections.append((f'HWPML 구역 {index} 내부 객체 · 미확인·수동 대조 필요',''))
    if not sections or not any(text.strip() for _,text in sections):
        raise ValueError('HWPML에 읽을 수 있는 본문이 없습니다.')
    return sections
