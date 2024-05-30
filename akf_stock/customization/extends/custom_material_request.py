import frappe
from erpnext.stock.doctype.material_request.material_request import MaterialRequest

class XMaterialRequest(MaterialRequest):
    def validate(self):
        super(XMaterialRequest, self).validate()
        self.stop_exceeding_qty()

    def stop_exceeding_qty(self):
        for row in self.items:
            result = frappe.db.sql(f""" Select sum(actual_qty) as qty
                        From `tabStock Ledger Entry`
                        Where docstatus=1
                        and item_code = '{row.item_code}'
                        and warehouse = '{row.from_warehouse}' 
                        -- having qty > {row.qty}""")
            if(result):
                if(result[0][0]<row.qty):
                    frappe.throw(f"In Row#{row.idx}: warehouse <b>{row.from_warehouse}</b>, item <b>{row.item_code}</b> quantity exceeded by <b>{result[0][0]} < {row.qty}</b>.")