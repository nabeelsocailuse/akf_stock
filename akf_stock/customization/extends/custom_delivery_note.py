import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from erpnext.stock.stock_ledger import make_sl_entries
from frappe.utils import getdate

class XDeliveryNote(DeliveryNote):
    def on_trash(self):
        pass
    
    def on_submit(self):
        super(XDeliveryNote, self).on_submit()
        self.make_stock_ledger_entry_target_warehouse()

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
    
    def on_cancel(self):
        super(XDeliveryNote, self).on_cancel()
        self.cancel_linked_records()

    def cancel_linked_records(self):
        name = frappe.db.get_value("Stock Entry", {"custom_delivery_note": self.name}, "name")
        if(name):
            frappe.db.sql(f""" 
            delete from `tabStock Ledger Entry` where voucher_no = '{name}'
        """)
            frappe.db.sql(f""" 
            delete from `tabStock Entry` where name = '{name}'
        """)
        
        frappe.db.sql(f""" 
            delete from `tabStock Ledger Entry` where voucher_no = '{self.name}'
        """)
        frappe.db.sql(f""" 
            delete from `tabGL Entry` where voucher_no = '{self.name}'
        """)
