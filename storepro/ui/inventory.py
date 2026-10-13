from .forms import Page,Field,Table,Dialog,button
from ..catalog import Catalog
from ..money import parse_money,parse_quantity,parse_quantity_zero,formatted


class ProductsPage(Page):
    def __init__(self,parent,app):
        super().__init__(parent,app,'المنتجات والمخزون')
        self.service=Catalog(app.db)
        self.query=Field(self.toolbar,'بحث')
        button(self.toolbar,'بحث / تحديث',self.refresh); button(self.toolbar,'إضافة',lambda:self.edit())
        button(self.toolbar,'تعديل المحدد',lambda:self.edit(self.table.selected())); button(self.toolbar,'تسوية مخزون',self.adjust)
        self.table=Table(self,['id','barcode','name','category','unit','cost_text','price_text','stock_text','minimum_text','active']); self.table.pack(fill='both',expand=True,padx=10,pady=10)
        self.refresh()
    def refresh(self):
        self.table.load([dict(p,cost_text=formatted(p['cost']),price_text=formatted(p['price']),stock_text=p['stock']/1000,minimum_text=p['min_stock']/1000) for p in self.service.search(self.query.get(),True)])
    def edit(self,p=None):
        p=p or {}
        fields={'name':('الاسم',p.get('name','')),'barcode':('الباركود',p.get('barcode') or ''),'category':('التصنيف',p.get('category','عام')),'unit':('الوحدة',p.get('unit','قطعة')),'cost':('تكلفة الوحدة',formatted(p.get('cost',0))),'price':('سعر البيع',formatted(p.get('price',0))),'min_stock':('حد التنبيه',str(p.get('min_stock',0)/1000)),'active':('الحالة','نشط' if p.get('active',1) else 'معطل',['نشط','معطل'])}
        def save(v):
            values=dict(v,id=p.get('id'),cost=parse_money(v['cost']),price=parse_money(v['price']),min_stock=parse_quantity_zero(v['min_stock']),active=v['active']=='نشط')
            self.service.save_product(self.app.actor,values); self.refresh()
        Dialog(self,'بيانات المنتج',fields,save)
    def adjust(self):
        p=self.table.selected()
        def save(v):
            qty=parse_quantity(v['qty']); qty=qty if v['direction']=='زيادة' else -qty
            self.service.adjust(self.app.actor,p['id'],qty,v['reason']); self.refresh()
        Dialog(self,'تسوية '+p['name'],{'direction':('الاتجاه','زيادة',['زيادة','نقص']),'qty':('الكمية','1'),'reason':('السبب','')},save)
