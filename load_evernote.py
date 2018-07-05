"""
Based on:
    http://www.hanxiaogang.com/writing/parsing-evernote-export-file-enex-using-python/
"""
from io import StringIO

from lxml import etree, html


p = etree.XMLParser(remove_blank_text=True, resolve_entities=False, encoding='utf-8')


def parseNoteXML(xmlFile):
    context = etree.iterparse(xmlFile, encoding='utf-8', strip_cdata=False, huge_tree=True)
    note_dict = {}
    notes = []
    for _, (_, elem) in enumerate(context):
        text = elem.text
        if elem.tag == 'content':
            text = []
            try:
                r = html.fromstring(elem.text.encode("utf-8"))
            except Exception as e:
                print(e)
                continue
            for e in r.iter():
                try:
                    text.append(e.text)
                except Exception as e:
                    print('cannot print')
                    raise e
        note_dict[elem.tag] = text
        if elem.tag == "note":
            notes.append(note_dict)
            note_dict = {}
    return notes


def test_parseNoteXML():
    from pprint import pprint
    notes = parseNoteXML('data/test/testnote.enex')
    assert len(notes) == 1
    assert notes[0]['content']
    pprint(notes[0])


def test_large():
    from pprint import pprint
    notes = parseNoteXML('/home/erb/Cosmosync/To Annex/Evernote.enex')
    assert notes[0]['content']
    pprint(notes[0])

