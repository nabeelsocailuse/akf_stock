import frappe
from erpnext.stock.doctype.material_request.material_request import MaterialRequest

class XMaterialRequest(MaterialRequest):
    def validate(self):
        super(XMaterialRequest, self).validate()
        self.stop_exceeding_qty()

    def stop_exceeding_qty(self):
        for row in self.items:
            if(row.actual_qty<row.qty):
                frappe.throw(f"In Row#{row.idx}: warehouse <b>{row.from_warehouse}</b>, item <b>{row.item_code}</b> quantity exceeded by <b>{row.actual_qty} < {row.qty}</b>.")