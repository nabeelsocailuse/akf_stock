import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

class XStockEntry(StockEntry):
    def on_submit(self):
        super(XStockEntry, self).on_submit()
        self.calculate_per_installed_for_delivery_note()

    def calculate_per_installed_for_delivery_note(self):
        if(not self.custom_delivery_note): return
        for d in self.items:     
            received_qty = frappe.db.sql(f""" 
                        select sum(-1 * actual_qty) as qty
                        from `tabStock Ledger Entry` 
                        where 
                            docstatus=1
                            and item_code = "{d.item_code}"
                            and warehouse = "{d.s_warehouse}" 
                            and voucher_no in (select name as qty
                                from `tabStock Entry` 
                                where docstatus=1 and custom_delivery_note ="{self.custom_delivery_note}")
                """)
            if(received_qty):
                actual_qty = frappe.db.sql(f"""  
                        Select sum(actual_qty) as actual_qty
                        From `tabStock Ledger Entry`
                        Where
                            docstatus<2
                            and item_code = "{d.item_code}"
                            and voucher_no = '{self.custom_delivery_note}'
                            and warehouse = '{d.s_warehouse}'
                    """)
                if(actual_qty):
                    received_qty = received_qty[0][0]
                    actual_qty = actual_qty[0][0]
                    if(actual_qty>0):
                        per_installed = (received_qty/actual_qty) * 100
                        # Material Request
                        custom_reference_name = frappe.db.get_value("Delivery Note", self.custom_delivery_note, "custom_reference_name")
                        frappe.db.set_value("Material Request", custom_reference_name, "per_ordered", per_installed)
                        # 
                        frappe.db.set_value("Delivery Note", self.custom_delivery_note, "per_installed", per_installed)
                        frappe.db.set_value("Delivery Note", self.custom_delivery_note, "per_billed", per_installed)
                        
                        if(per_installed>=100.0): 
                            frappe.db.set_value("Delivery Note", self.custom_delivery_note, "status", "Completed")
                            frappe.db.set_value("Material Request", custom_reference_name, "status", "Completed")
    
    def on_cancel(self):
        super(XStockEntry, self).on_cancel()
        self.cancel_linked_records()

    def cancel_linked_records(self):
        if (frappe.db.exists("Stock Ledger Entry", {"voucher_no": self.name})):
            frappe.db.sql(f""" 
                delete from `tabStock Ledger Entry` where voucher_no = '{self.name}'
            """)