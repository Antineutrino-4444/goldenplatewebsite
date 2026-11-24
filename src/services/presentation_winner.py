"""Paired native picture placeholders for the assembly's award announcement."""
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.parts.slide import SlideLayoutPart
from pptx.util import Pt


WINNER_MARKER = 'gp.winner'
WINNER_TEMPLATE_INDEX = 6
WINNER_PHOTOS = {
    21: ('gp.winner.photo.left', 'Student winner photo', 48),
    22: ('gp.winner.photo.right', 'Faculty winner photo', 748),
}


def add_winner_slide(presentation):
    # A real picture placeholder inherits its crop frame from a registered
    # layout. A styled rectangle or a slide-only p:ph cannot do that.
    master = presentation.slide_master
    package = presentation.part.package
    layout_xml = parse_xml(f'''
        <p:sldLayout {nsdecls("p", "a", "r")} type="cust" matchingName="{WINNER_MARKER}" preserve="1">
          <p:cSld name="{WINNER_MARKER}"><p:spTree>
            <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
            <p:grpSpPr/>
          </p:spTree></p:cSld>
          <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
        </p:sldLayout>''')
    layout_part = SlideLayoutPart(package.next_partname('/ppt/slideLayouts/slideLayout%d.xml'),
                                  CT.PML_SLIDE_LAYOUT, package, layout_xml)
    layout_part.relate_to(master.part, RT.SLIDE_MASTER)
    relationship = master.part.relate_to(layout_part, RT.SLIDE_LAYOUT)
    layout_ids = master._element.sldLayoutIdLst
    next_id = max(int(item.get('id')) for item in layout_ids.sldLayoutId_lst) + 1
    entry = layout_ids._add_sldLayoutId()
    entry.set('id', str(next_id))
    entry.rId = relationship
    layout = layout_part.slide_layout
    for idx, (name, description, x) in WINNER_PHOTOS.items():
        layout.shapes._spTree.add_placeholder(layout.shapes._next_shape_id, name, PP_PLACEHOLDER.PICTURE,
                                               'horz', 'full', idx)
        target = next(ph for ph in layout.placeholders if ph.placeholder_format.idx == idx)
        target.left, target.top, target.width, target.height = Pt(x), Pt(168), Pt(164), Pt(205)
        target._element.nvSpPr.cNvPr.set('descr', description)
    slide = presentation.slides.add_slide(layout)
    for idx, (name, description, _) in WINNER_PHOTOS.items():
        photo = slide.placeholders[idx]
        photo.name = name
        photo._element.nvSpPr.cNvPr.set('descr', description)
    slide._element.cSld.set('name', WINNER_MARKER)
    return slide
