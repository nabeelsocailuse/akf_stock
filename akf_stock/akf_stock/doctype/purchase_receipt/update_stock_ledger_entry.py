import frappe

def update_stock_ledger_entry(self):
    for row in self.items:
        if frappe.db.exists(
            "Stock Ledger Entry",
            {
                "docstatus": 1,
                "voucher_no": self.name,
            },
        ):
            frappe.db.sql(
                """ 
                UPDATE `tabStock Ledger Entry`
                SET custom_new = %s, custom_used = %s, custom_cost_center = %s, inventory_flag = %s, inventory_scenario = %s
                WHERE docstatus = 1 
                AND voucher_detail_no = %s
                AND voucher_no = %s
                """,
                (row.custom_new, row.custom_used, row.cost_center, row.inventory_flag, row.inventory_scenario, row.name, self.name)
            )