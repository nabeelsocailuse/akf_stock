import frappe
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt

class XPurchaseReceipt(PurchaseReceipt):
    def on_submit(self):
        super(XPurchaseReceipt, self).on_submit()
        self.update_stock_ledger_entry()

    def update_stock_ledger_entry(self):
        msg = ""
        for row in self.items:
            if(hasattr(row, "custom_new") and hasattr(row, "custom_used")):
                if(frappe.db.exists("Stock Ledger Entry", 
                    {"docstatus": 1, "item_code": row.item_code, "warehouse": row.warehouse})
                    ):
                    frappe.db.sql(f""" 
                            update `tabStock Ledger Entry`
                            set custom_new = {row.custom_new}, custom_used = {row.custom_used}
                            where docstatus=1 
                                and voucher_detail_no = '{row.name}'
                                and item_code = '{row.item_code}'
                                and warehouse = '{row.warehouse}'
                        """)
        