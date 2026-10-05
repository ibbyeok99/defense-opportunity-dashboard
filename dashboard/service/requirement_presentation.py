"""PPTX의 선언된 슬라이드 순서와 평문만 읽는다. 외부 자원·매크로는 실행하지 않는다."""
import posixpath
import re
from xml.etree import ElementTree as ET

MAX_XML = 8 * 1024 * 1024
MAX_SLIDES = 200
PRESENTATION_NAMESPACES = {
    'http://schemas.openxmlformats.org/presentationml/2006/main',
    'http://purl.oclc.org/ooxml/presentationml/main',
}


def _xml(archive, name):
    if archive.getinfo(name).file_size > MAX_XML:
        raise ValueError('PPTX 본문 크기 한도를 초과했습니다.')
    blob = archive.read(name)
    safe = blob.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in safe or b'<!ENTITY' in safe:
        raise ValueError('DTD·엔티티가 포함된 XML은 처리하지 않습니다.')
    return ET.fromstring(blob)


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _relations(archive, part):
    path = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part)+'.rels')
    if path not in archive.namelist():
        return {}
    rows = {}
    for node in _xml(archive, path):
        if _local(node.tag) != 'Relationship':
            continue
        key = node.get('Id')
        if not key or key in rows:
            raise ValueError('손상된 PPTX 관계 식별자입니다.')
        rows[key] = dict(node.attrib)
    return rows


def _target(part, relation):
    value = relation.get('Target', '')
    if (relation.get('TargetMode') == 'External' or not value or '\\' in value
            or re.search(r'^[A-Za-z]+:', value) or '?' in value or '#' in value):
        raise ValueError('외부 또는 확인되지 않은 PPTX 관계는 읽지 않습니다.')
    name = posixpath.normpath(value.lstrip('/') if value.startswith('/') else
                             posixpath.join(posixpath.dirname(part), value))
    if name.startswith('../') or name == '..':
        raise ValueError('손상된 PPTX 관계 경로입니다.')
    return name


def presentation_sections(archive):
    """메타데이터 XML을 미지원 문서로 세지 않는다. 이미지·객체 대조 공백은 보존한다."""
    names = archive.namelist()
    if len(names) != len(set(names)) or len(names) > 2048 or sum(i.file_size for i in archive.infolist()) > 64*1024*1024:
        raise ValueError('PPTX 압축 해제 한도를 초과했습니다.')
    if any('vbaproject' in name.lower() for name in names):
        raise ValueError('매크로 포함 문서는 수동 확인이 필요합니다.')
    part = 'ppt/presentation.xml'
    root = _xml(archive, part)
    if _local(root.tag) != 'presentation' or root.tag.partition('}')[0].lstrip('{') not in PRESENTATION_NAMESPACES:
        raise ValueError('손상된 PPTX 본문 구조입니다.')
    relationships = _relations(archive, part)
    slides = []
    for node in root.iter():
        if _local(node.tag) != 'sldId':
            continue
        rid = next((v for k, v in node.attrib.items() if k.endswith('}id')), '')
        relation = relationships.get(rid, {})
        if not relation.get('Type', '').endswith('/slide'):
            raise ValueError('손상된 PPTX 슬라이드 관계입니다.')
        target = _target(part, relation)
        if not re.fullmatch(r'ppt/slides/slide\d+\.xml', target) or target not in names or target in slides:
            raise ValueError('손상된 PPTX 슬라이드 순서입니다.')
        slides.append(target)
    if not slides or len(slides) > MAX_SLIDES:
        raise ValueError('PPTX 슬라이드 수 한도를 초과했습니다.')
    sections = []
    for index, slide in enumerate(slides, 1):
        body = _xml(archive, slide)
        if _local(body.tag) != 'sld':
            raise ValueError('손상된 PPTX 슬라이드 본문입니다.')
        paragraphs = []
        for node in body.iter():
            if _local(node.tag) == 'p':
                paragraphs.append(''.join((child.text or '') if _local(child.tag)=='t' else '\n'
                                          if _local(child.tag)=='br' else '' for child in node.iter()))
        sections.append((f'{index}슬라이드', '\n'.join(paragraphs)))
        relations = _relations(archive, slide)
        for node in body.iter():
            if _local(node.tag) == 'blip':
                rid = next((v for k,v in node.attrib.items() if _local(k) in {'embed','link'}), '')
                relation = relations.get(rid, {})
                try:
                    image = _target(slide, relation)
                    if image not in names or not relation.get('Type','').endswith('/image'):
                        raise ValueError('이미지 관계 미확인')
                    label = image
                except ValueError:
                    label = '외부·누락 이미지'
                sections.append((f'{index}슬라이드 내부 이미지 {label} · 미확인·수동 대조 필요', ''))
            elif _local(node.tag) in {'oleObj','chart','contentPart','videoFile','audioFile'}:
                sections.append((f'{index}슬라이드 내부 객체 · 미확인·수동 대조 필요', ''))
        if body.get('show') == '0':
            sections.append((f'{index}슬라이드 숨김 설정 · 미확인·수동 대조 필요', ''))
    orphaned = set(n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml', n))-set(slides)
    if orphaned:
        sections.append(('본문 순서에 없는 슬라이드 · 미확인·수동 대조 필요',''))
    # 이미지·내장 객체가 없는 관계 파일의 외부 링크도 자동으로 열지 않는다.
    return sections
