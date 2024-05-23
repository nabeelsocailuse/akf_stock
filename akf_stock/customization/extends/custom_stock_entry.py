import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry

class XStockEntry(StockEntry):
    def on_submit(self):
        super(XStockEntry, self).on_submit()
        self.calculate_per_installed_for_delivery_note()

    def calculate_per_installed_for_delivery_note(self):
        if(not self.custom_delivery_note): return
        total_received_qty = 0.0
        total_actual_qty = 0.0
        for row in self.items:     
            received_qty = self.get_receive_lost_qty(row)
            if(received_qty):
                total_received_qty += received_qty[0][0]
                actual_qty = self.get_actual_qty(row)
                if(actual_qty): total_actual_qty += actual_qty[0][0]
        
        return self.set_percent_delivery_note_material_request_status(total_received_qty, total_actual_qty)
    
    def get_receive_lost_qty(self, row):
        return frappe.db.sql(f""" 
            select ifnull(sum(-1 * actual_qty),0) as qty
            from `tabStock Ledger Entry` 
            where 
                docstatus=1
                and item_code = "{row.item_code}"
                and warehouse = "{row.s_warehouse}" 
                and voucher_no in (select name as qty
                    from `tabStock Entry` 
                    where docstatus=1 and stock_entry_type = "{self.stock_entry_type}" and custom_delivery_note ="{self.custom_delivery_note}")
        """)
    
    def get_actual_qty(self, row):
        return frappe.db.sql(f"""  
                Select ifnull(sum(actual_qty),0) as actual_qty
                From `tabStock Ledger Entry`
                Where
                    docstatus<2
                    and item_code = "{row.item_code}"
                    and voucher_no = '{self.custom_delivery_note}'
                    and warehouse = '{row.s_warehouse}'
            """)
        
    def set_percent_delivery_note_material_request_status(self, total_received_qty, total_actual_qty):
        per_installed = (total_received_qty / total_actual_qty) * 100 if(total_actual_qty>0) else 0.0
        
        if(self.stock_entry_type=="Material Transfer"):
            frappe.db.sql(f""" 
                update `tabDelivery Note`
                set per_installed = {per_installed}, per_billed = {per_installed}
                where name = '{self.custom_delivery_note}'
            """)
        elif(self.stock_entry_type=="Lost / Wastage"):
            frappe.db.set_value("Delivery Note", self.custom_delivery_note, "custom_lost_wastage", per_installed)
        
        self.update_status_delivery_note_and_material_request()
        
        return per_installed
    
    def update_status_delivery_note_and_material_request(self):
        
        total_percent = frappe.db.sql(f""" 
            Select ifnull((per_installed + custom_lost_wastage),0) as total_percent
            From `tabDelivery Note`
            where name = '{self.custom_delivery_note}'
        """, as_dict=0)
        
        if(total_percent):
            if(total_percent[0][0]==100):
                frappe.db.set_value("Delivery Note", self.custom_delivery_note, "status", "Completed")
                custom_reference_name = frappe.db.get_value("Delivery Note", self.custom_delivery_note, "custom_reference_name")
                frappe.db.set_value("Material Request", custom_reference_name, "status", "Completed")
            else:
                frappe.db.set_value("Delivery Note", self.custom_delivery_note, "status", "To Receive")
                custom_reference_name = frappe.db.get_value("Delivery Note", self.custom_delivery_note, "custom_reference_name")
                frappe.db.set_value("Material Request", custom_reference_name, "status", "Transferred")

    def on_trash(self):
        pass

    def on_cancel(self):
        super(XStockEntry, self).on_cancel()
        self.cancel_linked_records()
        self.reset_delivery_note_percent()

    def cancel_linked_records(self):
        if (frappe.db.exists("Stock Ledger Entry", {"voucher_no": self.name})):
            frappe.db.sql(f""" 
                delete from `tabStock Ledger Entry` where voucher_no = '{self.name}'
            """)
        if (frappe.db.exists("GL Entry", {"voucher_no": self.name})):
            frappe.db.sql(f""" 
                delete from `tabGL Entry` where voucher_no = '{self.name}'
            """)
    
    def reset_delivery_note_percent(self):
        if(not self.custom_delivery_note): return

        per_installed = self.calculate_per_installed_for_delivery_note()
        if(self.stock_entry_type == "Lost / Wastage"):
            frappe.db.sql(f""" 
                update `tabDelivery Note`
                set custom_lost_wastage = custom_lost_wastage - {per_installed}
                where name = '{self.custom_delivery_note}'
            """)
        else:
            frappe.db.sql(f""" 
                update `tabDelivery Note`
                set per_installed = per_installed - {per_installed}
                where name = '{self.custom_delivery_note}'
            """)

