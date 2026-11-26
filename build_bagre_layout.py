"""Build portable QGIS project and A3 layout from published common-grid rasters."""
import os
import sys
from pathlib import Path
import shutil

mac = Path("/Applications/QGIS.app/Contents/Resources/qgis")
if mac.is_dir():
    os.environ.setdefault("PROJ_DATA", str(mac/"proj"))
    os.environ.setdefault("PROJ_LIB", str(mac/"proj"))
from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

source, out = map(lambda p: Path(p).resolve(), sys.argv[1:3])
out.mkdir(parents=True,exist_ok=True)
rasters=out/"rasters"
rasters.mkdir(exist_ok=True)
app=QgsApplication([],False)
if mac.is_dir(): app.setPrefixPath(str(mac),True)
app.initQgis()
project=QgsProject.instance()
crs=QgsCoordinateReferenceSystem("EPSG:32630")
project.setCrs(crs)
INK="#173c42"
et_colors=["#ffffd9","#c7e9b4","#7fcdbb","#41b6c4","#225ea8","#081d58"]
diff_colors=["#e5eff6","#c6dbef","#9ecae1","#4292c6","#08519c","#08306b"]
ndvi_colors=["#a50026","#f46d43","#fee08b","#d9ef8b","#66bd63","#006837"]
def layer(name,label,lo,hi,colors):
    path=rasters/name
    shutil.copy2(source/name,path)
    l=QgsRasterLayer(str(path),label)
    assert l.isValid() and l.crs().authid()=="EPSG:32630" and (l.width(),l.height())==(28,26),name
    shader=QgsColorRampShader(lo,hi)
    shader.setColorRampType(QgsColorRampShader.Interpolated)
    shader.setColorRampItemList([QgsColorRampShader.ColorRampItem(lo+(hi-lo)*i/(len(colors)-1),QColor(c),"") for i,c in enumerate(colors)])
    rs=QgsRasterShader(lo,hi)
    rs.setRasterShaderFunction(shader)
    r=QgsSingleBandPseudoColorRenderer(l.dataProvider(),1,rs)
    r.setClassificationMin(lo); r.setClassificationMax(hi)
    l.setRenderer(r); project.addMapLayer(l)
    return l
mod=layer("mod16_2021-04.tif","MOD16 ET (mm/month)",0,280,et_colors)
wap=layer("wapor_2021-04.tif","WaPOR AETI (mm/month)",0,280,et_colors)
dif=layer("et_difference_2021-04.tif","WaPOR minus MOD16 (mm/month)",0,180,diff_colors)
ndv=layer("ndvi_2021-04.tif","Sentinel-2 NDVI",-.5,.8,ndvi_colors)
for l in (wap,dif,ndv):
    assert l.extent()==mod.extent()
    project.layerTreeRoot().findLayer(l.id()).setItemVisibilityChecked(False)
project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(mod.extent(),crs))
layout=QgsPrintLayout(project); layout.initializeDefaults(); layout.setName("Bagré ET intercomparison | April 2021")
layout.pageCollection().pages()[0].setPageSize("A3",QgsLayoutItemPage.Landscape)
layout.renderContext().setDpi(240)
def place(it,x,y,w,h):
    layout.addLayoutItem(it);it.attemptMove(QgsLayoutPoint(x,y));it.attemptResize(QgsLayoutSize(w,h));return it
def label(s,x,y,w,h,size=10,bold=False):
    it=QgsLayoutItemLabel(layout);it.setText(s);it.setMargin(0)
    f=QFont("Helvetica Neue");f.setPointSizeF(size);f.setBold(bold);it.setFont(f)
    it.setFontColor(QColor(INK));it.setVAlign(Qt.AlignVCenter)
    return place(it,x,y,w,h)
def box(x,y,w,h,c):
    it=QgsLayoutItemShape(layout);it.setShapeType(QgsLayoutItemShape.Rectangle)
    it.setSymbol(QgsFillSymbol.createSimple({"color":c,"outline_style":"no"}))
    return place(it,x,y,w,h)
def drawmap(l,x,y,title):
    label(title,x,y-8,126,6,13,True)
    it=QgsLayoutItemMap(layout); place(it,x,y,116,107.714)
    it.setCrs(crs);it.setLayers([l]);it.setKeepLayerSet(True);it.storeCurrentLayerStyles();it.setKeepLayerStyles(True)
    it.zoomToExtent(mod.extent());it.setFrameEnabled(True);it.setFrameStrokeColor(QColor("#9ca8ab"))
    return it
def ramp(x,y,colors,lo,hi,unit):
    for i in range(80):
        t=(i+.5)/80*(len(colors)-1);j=min(int(t),len(colors)-2);f=t-j
        a,b=QColor(colors[j]),QColor(colors[j+1])
        c=QColor(*[round(u+(v-u)*f) for u,v in zip(a.getRgb()[:3],b.getRgb()[:3])])
        box(x+i*1.2,y,1.21,4,c.name())
    label(str(lo),x,y+4,25,5,9)
    label(str(hi)+" "+unit,x+75,y+4,56,5,9)
label("Satellite evapotranspiration in Bagré, Burkina Faso",14,5,390,12,23,True)
label("April 2021 | MOD16 and WaPOR intercomparison | 500 m common grid",14,17,390,8,13)
m=drawmap(mod,14,37,"A. MOD16 actual ET")
drawmap(wap,145,37,"B. WaPOR actual ET + interception")
drawmap(dif,14,166,"C. WaPOR minus MOD16")
drawmap(ndv,145,166,"D. Vegetation activity (NDVI)")
# legends in right-hand column, separated from maps
label("How to read the maps",280,34,126,8,15,True)
label("A and B | Water depth (same scale)",280,44,126,6,11,True)
ramp(280,53,et_colors,0,280,"mm/month")
label("C | Difference, cells ≥50% cropland",280,69,126,6,11,True)
ramp(280,78,diff_colors,0,180,"mm/month")
label("D | Monthly Sentinel-2 NDVI",280,94,126,6,11,True)
ramp(280,103,ndvi_colors,-.5,.8,"")
label("White = missing or outside comparison domain.",280,119,126,6,9)
box(280,130,126,.4,"#a0aaaa")
label("April paired comparison",280,134,126,8,15,True)
label("317 crop-dominated cells",280,144,126,6,11)
label("Mean ET: MOD16 2.23 | WaPOR 35.04 mm",280,154,126,6,11)
label("Mean difference: +32.80 mm | r = 0.902",280,163,126,6,11)
label("NDVI ≥0.35 (n=32): 10.11 vs 140.96 mm",280,172,126,6,11,True)
label("Native pixel audit confirms the discrepancy.",280,181,126,6,10)
label("Reference ET0: 206.30 mm (ERA5-Land)",280,190,126,6,10)
label("Agreement is not validation; neither product",280,200,126,6,10)
label("is established as more accurate locally.",280,207,126,6,10)
label("No field-level irrigation or stress diagnosis.",280,217,126,6,10)
label("↑ N (grid north)",280,234,126,7,12,True)
scale=QgsLayoutItemScaleBar(layout);scale.setStyle("Single Box");scale.setLinkedMap(m);scale.applyDefaultSize()
scale.setUnits(Qgis.DistanceUnit.Kilometers);scale.setUnitsPerSegment(2);scale.setNumberOfSegments(2);scale.setNumberOfSegmentsLeft(0)
scale.setUnitLabel("km");scale.setHeight(2);scale.setFont(QFont("Helvetica Neue",10));layout.addLayoutItem(scale);scale.attemptMove(QgsLayoutPoint(280,245))
layout.setReferenceMap(m)
box(14,280,392,.3,"#a0aaaa")
label("Sources: MODIS MOD16A2GF v061; FAO WaPOR v3; Sentinel-2 SR; ESA WorldCover 2021; ERA5-Land. 160 km² pilot, WGS 84 / UTM 30N.",14,282,392,6,9)
label("Ibrahim Kabore | November 2026 | Exploratory remote sensing study; no independent field validation.",14,289,392,6,9)
project.layoutManager().addLayout(layout)
project.setFilePathStorage(Qgis.FilePathType.Relative)
project.setFileName(str(out/"Bagre_ET_April_2021.qgz"))
assert project.write()
export=QgsLayoutExporter(layout);img=QgsLayoutExporter.ImageExportSettings();img.dpi=240
pdf=QgsLayoutExporter.PdfExportSettings();pdf.dpi=240
assert export.exportToImage(str(out/"Bagre_ET_April_2021.png"),img)==QgsLayoutExporter.Success
assert export.exportToPdf(str(out/"Bagre_ET_April_2021.pdf"),pdf)==QgsLayoutExporter.Success
print("QGIS project and PDF/PNG exported")
