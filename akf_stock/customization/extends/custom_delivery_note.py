import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from erpnext.stock.stock_ledger import make_sl_entries
from frappe.utils import getdate

class XDeliveryNote(DeliveryNote):
    def on_trash(self):
        pass
    
    def on_submit(self):
        super(XDeliveryNote, self).on_submit()
        self.if_custom_add_to_transit()
 
    def if_custom_add_to_transit(self):
        
        if(self.custom_add_to_transit):
            self.update_status()
            self.make_stock_ledger_entry_target_warehouse()

    def update_status(self):
        frappe.db.set_value("Delivery Note", self.name, "status", "To Receive")
    
    def make_stock_ledger_entry_target_warehouse(self):
        sl_entries = []
        entry = frappe._dict({
            "doctype": "Stock Ledger Entry",
            "warehouse": self.custom_set_in_transit_warehouse,
            "voucher_type": "Delivery Note",
            "voucher_no": self.name,
            "posting_date": self.posting_date,
            "posting_time": self.posting_time,
        })
        for d in self.items:
           entry.update({
                "item_code": d.item_code,
                "actual_qty": d.qty,
                "stock_uom": d.uom,
                "incoming_rate": d.incoming_rate,
                "valuation_rate": d.incoming_rate
            })
        sl_entries.append(entry)
        make_sl_entries(sl_entries)
    
    def on_trash(self):
        self.cancel_linked_records()

    def on_cancel(self):
        super(XDeliveryNote, self).on_cancel()
        self.cancel_linked_records()

    def cancel_linked_records(self):
        self.delete_stock_entry_and_ledger()
        self.delete_stock_ledger_and_gl_entry()
        self.reset_material_request()
    
    def delete_stock_entry_and_ledger(self):
        stock = frappe.db.get_list("Stock Entry", filters={"custom_delivery_note": self.name}, fields=["name"])
        if(stock):
            for d in stock:
                frappe.db.sql(f""" 
                delete from `tabStock Ledger Entry` where voucher_no = '{d.name}'
            """)
                frappe.db.sql(f""" 
                delete from `tabStock Entry` where name = '{d.name}'
            """)
    
    def delete_stock_ledger_and_gl_entry(self):
        frappe.db.sql(f""" 
            delete from `tabStock Ledger Entry` where voucher_no = '{self.name}'
        """)
        frappe.db.sql(f""" 
            delete from `tabGL Entry` where voucher_no = '{self.name}'
        """)

    def reset_material_request(self):
        if(not self.custom_reference_name): return
        frappe.db.sql(f""" 
                update `tab{self.custom_reference_doctype}`
                set status = "Pending", per_ordered=0
                where name = '{self.custom_reference_name}'
            """)

