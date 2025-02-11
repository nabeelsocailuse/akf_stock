import frappe
import json
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt


class XStockEntry(StockEntry):
    def before_validate(self):
        super(XStockEntry, self).before_validate()
        self.set_warehouse_cost_centers()

    def validate(self):
        super(XStockEntry, self).validate()
        self.validate_difference_account()
        self.set_warehouse_cost_centers()
        self.set_total_quantity_count()
        self.set_actual_quantity_before_submission()

    def set_actual_quantity_before_submission(self):
            for item in self.items:
                    item.custom_actual_quantity = item.actual_qty
                    
    def on_submit(self):
        super(XStockEntry, self).on_submit()
        self.calculate_per_installed_for_delivery_note()
        self.set_material_request_status_per_outgoing_stock_entry()
        self.update_stock_ledger_entry()
        self.create_gl_entries_for_stock_entry()
        self.set_total_quantity_count()

        self.create_asset_item_and_asset()
    

    def create_asset_item_and_asset(self):
        stock_entry = frappe.get_doc("Stock Entry", self.name)

        if stock_entry.stock_entry_type != "Inventory to Asset":
            return

        created_assets = []

        for item in stock_entry.items:
            item_code = item.item_code
            item_name = item.item_name            
            asset_item_code = frappe.db.exists("Item", {"item_name":f"Asset-{item_name}"})
            asset_category = frappe.db.exists("Asset Category", {"asset_category_name": item.item_group})

            if not asset_category:
                asset_category = frappe.get_doc({
                    "doctype": "Asset Category",
                    "asset_category_name": item.item_group,
                    "accounts": 
                        [{
                            "company_name": stock_entry.company,
                            "fixed_asset_account": "Capital Equipments - AKFP"
                        }]
                    })
                asset_category.insert()
                frappe.db.commit()

            if not asset_item_code:
                asset_item_doc = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": f"Asset-{item_name}",
                    "item_name": f"Asset-{item_name}",
                    "item_group": asset_category, 
                    "stock_uom": item.uom,
                    "is_stock_item": 0,
                    "is_fixed_asset": 1, 
                    "asset_category": asset_category,  
                })
                
                asset_item_doc.insert()
                frappe.db.commit()
                asset_item_code = asset_item_doc.name
                

            asset = frappe.get_doc({
                "doctype": "Asset",
                "item_code": asset_item_code,
                "company": stock_entry.company,
                "location": item.custom_asset_location,
                "custom_source_of_asset_acquistion": 'Normal',
                "available_for_use_date": frappe.utils.nowdate(),
                "gross_purchase_amount": item.basic_rate,
                "asset_quantity": item.qty,
                "is_existing_asset": 1
            })
            asset.insert()
            frappe.db.commit()
            created_assets.append(item_code)

        if created_assets:
            return f"Assets created for items: {', '.join(created_assets)}"
        return "No new assets created."


    def calculate_per_installed_for_delivery_note(self):
        if not self.custom_delivery_note:
            return
        total_received_qty = 0.0
        total_actual_qty = 0.0
        for row in self.items:
            received_qty = self.get_receive_lost_qty(row)
            if received_qty:
                total_received_qty += received_qty[0][0]
                actual_qty = self.get_actual_qty(row)
                if actual_qty:
                    total_actual_qty += actual_qty[0][0]

        return self.set_percent_delivery_note_material_request_status(
            total_received_qty, total_actual_qty
        )

    def get_receive_lost_qty(self, row):
        return frappe.db.sql(
            f""" 
            select ifnull(sum(-1 * actual_qty),0) as qty
            from `tabStock Ledger Entry` 
            where 
                docstatus=1
                and item_code = "{row.item_code}"
                and warehouse = "{row.s_warehouse}" 
                and voucher_no in (select name as qty
                    from `tabStock Entry` 
                    where docstatus=1 and stock_entry_type = "{self.stock_entry_type}" and custom_delivery_note ="{self.custom_delivery_note}")
        """
        )

    def get_actual_qty(self, row):
        return frappe.db.sql(
            f"""  
                Select ifnull(sum(actual_qty),0) as actual_qty
                From `tabStock Ledger Entry`
                Where
                    docstatus<2
                    and item_code = "{row.item_code}"
                    and voucher_no = '{self.custom_delivery_note}'
                    and warehouse = '{row.s_warehouse}'
            """
        )

    def set_percent_delivery_note_material_request_status(
        self, total_received_qty, total_actual_qty
    ):
        per_installed = (
            (total_received_qty / total_actual_qty) * 100
            if (total_actual_qty > 0)
            else 0.0
        )

        if self.stock_entry_type == "Material Transfer":
            frappe.db.sql(
                f""" 
                update `tabDelivery Note`
                set per_installed = {per_installed}, per_billed = {per_installed}
                where name = '{self.custom_delivery_note}'
            """
            )
        elif self.stock_entry_type == "Lost / Wastage":
            frappe.db.set_value(
                "Delivery Note",
                self.custom_delivery_note,
                "custom_lost_wastage",
                per_installed,
            )

        self.update_status_delivery_note_and_material_request()

        return per_installed

    def update_status_delivery_note_and_material_request(self):

        total_percent = frappe.db.sql(
            f""" 
            Select ifnull((per_installed + custom_lost_wastage),0) as total_percent
            From `tabDelivery Note`
            where name = '{self.custom_delivery_note}'
        """,
            as_dict=0,
        )

        if total_percent:
            percent = total_percent[0][0]

            d_status = "To Receive"
            transfer_status = "In Transit"
            m_status = "Partially Received"

            if percent == 100:
                d_status = "Completed"
                transfer_status = "Completed"
                m_status = "Received"

            # Delivery Note
            frappe.db.sql(
                f""" 
                    update `tabDelivery Note`
                    set status="{d_status}"
                    where docstatus =1 
                        and name ="{self.custom_delivery_note}"
                """
            )

            # Material Request
            frappe.db.sql(
                f""" 
                    update `tabMaterial Request`
                    set transfer_status ="{transfer_status}" ,status="{m_status}", per_ordered =  {percent}
                    where name in (select custom_reference_name from `tabDelivery Note` where name="{self.custom_delivery_note}")
                """
            )

    def set_material_request_status_per_outgoing_stock_entry(self):
        if not self.outgoing_stock_entry:
            return
        actual_qty = 0.0
        received_qty = 0.0
        for row in self.items:
            _actual_qty = frappe.db.sql(
                f""" Select sum(actual_qty) as qty
                        From `tabStock Ledger Entry`
                        Where docstatus=1
                        and item_code = '{row.item_code}'
                        and warehouse = '{row.s_warehouse}' 
                        and voucher_no = '{self.outgoing_stock_entry}' """
            )

            if _actual_qty:
                actual_qty += _actual_qty[0][0]

            _received_qty = frappe.db.sql(
                f""" 
                    select ifnull(sum(actual_qty),0) as qty
                    from `tabStock Ledger Entry` 
                    where 
                        docstatus=1
                        and item_code = "{row.item_code}"
                        and warehouse = "{row.s_warehouse}" 
                        and voucher_no in (select name as qty
                            from `tabStock Entry` 
                            where docstatus=1 and outgoing_stock_entry ="{self.outgoing_stock_entry}")
                """
            )

            if _received_qty:
                _received_qty = _received_qty[0][0]
                received_qty += (
                    (-1 * _received_qty) if (_received_qty < 0) else _received_qty
                )

        if actual_qty > 0:
            per_ordered = (received_qty / actual_qty) * 100.0
            status = "Completed" if (per_ordered == 100) else "In Transit"
            frappe.db.sql(
                f""" 
                        Update `tabMaterial Request`
                        set transfer_status = "{status}",status = "{status}", per_ordered = {per_ordered}
                        Where name in (Select material_request 
                        From `tabStock Entry Detail` 
                        Where docstatus=1 and parent="{self.outgoing_stock_entry}" )"""
            )

    def update_stock_ledger_entry(self):
        source_cost_center, target_cost_center = "", ""
        # for item in self.items:
            

        for row in self.items:
            if frappe.db.exists(
                "Stock Ledger Entry",
                {
                    "docstatus": 1,
                    "voucher_no": self.name,
                },
            ):
                if self.purpose == "Material Receipt":
                    target_warehouse = row.t_warehouse
                    target_cost_center = frappe.db.get_value(
                        "Warehouse", target_warehouse, "custom_cost_center"
                    )
                    frappe.db.sql(
                    f""" 
                        UPDATE `tabStock Ledger Entry`
                        SET custom_new = {row.custom_new}, custom_used = {row.custom_used}, custom_target_service_area='{row.to_program}', custom_target_subservice_area='{row.to_subservice_area}', custom_target_product='{row.to_product}', custom_target_project='{row.custom_target_project}', inventory_flag='{row.inventory_flag}', inventory_scenario='{row.inventory_scenario}', custom_cost_center='{target_cost_center}', custom_department='{self.custom_department}'
                        WHERE docstatus=1 
                            and voucher_detail_no = '{row.name}'
                            and voucher_no = '{self.name}'
                    """
                )
                elif self.purpose == "Material Issue":
                    source_warehouse = row.s_warehouse
                    source_cost_center = frappe.db.get_value(
                        "Warehouse", source_warehouse, "custom_cost_center"
                    )
                    frappe.db.sql(
                    f""" 
                        UPDATE `tabStock Ledger Entry`
                        SET custom_new = {row.custom_new}, custom_used = {row.custom_used}, custom_target_service_area='{row.to_program}', custom_target_subservice_area='{row.to_subservice_area}', custom_target_product='{row.to_product}', custom_target_project='{row.custom_target_project}', inventory_flag='{row.inventory_flag}', inventory_scenario='{row.inventory_scenario}', custom_cost_center='{source_cost_center}', custom_department='{self.custom_department}'
                        WHERE docstatus=1 
                            and voucher_detail_no = '{row.name}'
                            and voucher_no = '{self.name}'
                    """)
                elif self.purpose == "Material Transfer":
                    source_warehouse = row.s_warehouse
                    source_cost_center = frappe.db.get_value(
                        "Warehouse", source_warehouse, "custom_cost_center"
                    )
                    frappe.db.sql(
                    f""" 
                        UPDATE `tabStock Ledger Entry`
                        SET custom_new = {row.custom_new}, custom_used = {row.custom_used}, custom_target_service_area='{row.to_program}', custom_target_subservice_area='{row.to_subservice_area}', custom_target_product='{row.to_product}', custom_target_project='{row.custom_target_project}', inventory_flag='{row.inventory_flag}', inventory_scenario='{row.inventory_scenario}', custom_cost_center='{source_cost_center}', custom_department='{self.custom_department}'
                        WHERE docstatus=1 
                            and voucher_detail_no = '{row.name}'
                            and voucher_no = '{self.name}'
                            and warehouse= '{row.s_warehouse}'
                    """)

                    target_warehouse = row.t_warehouse
                    target_cost_center = frappe.db.get_value(
                        "Warehouse", target_warehouse, "custom_cost_center"
                    )
                    frappe.db.sql(
                    f""" 
                        UPDATE `tabStock Ledger Entry`
                        SET custom_new = {row.custom_new}, custom_used = {row.custom_used}, custom_target_service_area='{row.to_program}', custom_target_subservice_area='{row.to_subservice_area}', custom_target_product='{row.to_product}', custom_target_project='{row.custom_target_project}', inventory_flag='{row.inventory_flag}', inventory_scenario='{row.inventory_scenario}', custom_cost_center='{target_cost_center}', custom_department='{self.custom_department}'
                        WHERE docstatus=1 
                            and voucher_detail_no = '{row.name}'
                            and voucher_no = '{self.name}'
                            and warehouse= '{row.t_warehouse}'
                    """)
                

        if self.custom_donor_ids:
            # Initialize an empty list to store child values
            child_values = []
            donor_names = []

            # Fetch child table records for the current parent document
            child_records = frappe.get_all(
                "Donor List",
                filters={"parent": self.name},
                fields=["donor"],
            )

            # Loop through each child record and process the values
            for child in child_records:
                child_values.append(child.donor)
                donor=frappe.db.get_value('Donor',child.donor,'donor_name')
                donor_names.append(donor)

            if frappe.db.exists(
                "Stock Ledger Entry",
                {
                    "docstatus": 1,
                    "voucher_no": self.name,
                },
            ):
                child_values_as_string = json.dumps(child_values)
                frappe.db.sql(
                    f""" 
                            update 
                                `tabStock Ledger Entry`
                            set 
                                custom_donor_list = '{child_values_as_string}'
                            where 
                                docstatus=1 
                                and voucher_no = '{self.name}'
                        """
                )

                donor_names_as_string = json.dumps(donor_names)
                frappe.db.sql(
                    f""" 
                            update 
                                `tabStock Ledger Entry`
                            set 
                                custom_donor_name_list = '{donor_names_as_string}'
                            where 
                                docstatus=1 
                                and voucher_no = '{self.name}'
                        """
                )

                

    def on_trash(self):
        self.cancel_linked_records()
        self.reset_delivery_note_percent()

    def on_cancel(self):
        super(XStockEntry, self).on_cancel()
        self.cancel_linked_records()
        self.reset_delivery_note_percent()

    def cancel_linked_records(self):
        if frappe.db.exists("Stock Ledger Entry", {"voucher_no": self.name}):
            frappe.db.sql(
                f""" 
                delete from `tabStock Ledger Entry` where voucher_no = '{self.name}'
            """
            )
        if frappe.db.exists("GL Entry", {"voucher_no": self.name}):
            frappe.db.sql(
                f""" 
                delete from `tabGL Entry` where voucher_no = '{self.name}'
            """
            )

    def reset_delivery_note_percent(self):
        if not self.custom_delivery_note:
            return

        per_installed = self.calculate_per_installed_for_delivery_note()
        if self.stock_entry_type == "Lost / Wastage":
            frappe.db.sql(
                f""" 
                update `tabDelivery Note`
                set custom_lost_wastage = custom_lost_wastage - {per_installed}
                where name = '{self.custom_delivery_note}'
            """
            )
        else:
            frappe.db.sql(
                f""" 
                update `tabDelivery Note`
                set per_installed = per_installed - {per_installed}
                where name = '{self.custom_delivery_note}'
            """
            )

    def validate_difference_account(self):
        company = frappe.get_doc("Company", self.company)
        for d in self.get("items"):
            d.expense_account = company.custom_default_inventory_fund_account

    # or (self.purpose == "Material Transfer" and self.outgoing_stock_entry)
    def validate_qty(self):
        super(XStockEntry, self).validate_qty()
        if ((self.purpose == "Material Issue") or (self.purpose == "Material Transfer")):
            for item in self.items:
                condition_parts = [
                    (
                        f" and custom_new = {item.custom_new} "
                        if item.custom_new
                        else " and custom_new = 0 "
                    ),
                    (
                        f" and custom_used = {item.custom_used} "
                        if item.custom_used
                        else " and custom_used = 0 "
                    ),
                    (
                        f" and warehouse = '{item.s_warehouse}' "
                        if item.s_warehouse
                        else " and warehouse IS NULL "
                    ),
                    (
                        f" and custom_cost_center = '{item.cost_center}' "
                        if item.cost_center
                        else " and custom_cost_center IS NULL "
                    ),
                    (
                        f" and inventory_flag = '{item.inventory_flag}' "
                        if item.inventory_flag
                        else "Normal"
                    ),
                    (
                        f" and inventory_scenario = '{item.inventory_scenario}' "
                        if item.inventory_scenario
                        else "Normal"
                    ),
                    (
                        f" and program = '{item.program}' "
                        if item.program
                        else " and program IS NULL "
                    ),
                    (
                        f" and subservice_area = '{item.subservice_area}' "
                        if item.subservice_area
                        else " and subservice_area IS NULL "
                    ),
                    (
                        f" and product = '{item.product}' "
                        if item.product
                        else " and product IS NULL "
                    ),
                    (
                        f" and project = '{item.project}' "
                        if item.project
                        else " and project IS NULL "
                    ),
                ]
                condition = "  ".join(condition_parts)

                query = f"""
                        SELECT ifnull(SUM(actual_qty),0) as donated_qty,
                            item_code
                        FROM `tabStock Ledger Entry`
                        WHERE
                            item_code='{item.item_code}'
                            {f'{condition}' if condition else ''}
                    """
                # frappe.throw(f"query: {query}")
                
                try:
                    donated_invetory = frappe.db.sql(
                        query,
                        as_dict=True,
                    )
                except Exception as e:
                    frappe.throw(f"Error executing query: {e}")

                for di in donated_invetory:
                    if di.donated_qty >= item.qty:
                        pass
                    else:
                        frappe.throw(
					f"Insufficient quantity for item {item.item_code}. "
					f"Requested quantity: {item.qty}, Available quantity: {di.donated_qty}"
					)

    def create_gl_entries_for_stock_entry(self):
        debit_account, credit_account = "", ""

        company = frappe.get_doc("Company", self.company)
        if self.stock_entry_type == "Donated Inventory Receive - Restricted":
            pass

        elif self.stock_entry_type == "Inventory Consumption - Restricted":
            debit_account = company.custom_default_inventory_expense_account
            credit_account = company.default_income_account

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")

            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_outgoing_value,
                    "credit": 0,
                    "debit_in_account_currency": self.total_outgoing_value,
                    "credit_in_account_currency": 0,
                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "credit": self.total_outgoing_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_outgoing_value,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()

        elif self.stock_entry_type == "Inventory Transfer - Restricted":

            source_cost_center, target_cost_center = "", ""
            for item in self.items:
                source_warehouse = item.s_warehouse
                source_cost_center = frappe.db.get_value(
                    "Warehouse", source_warehouse, "custom_cost_center"
                )

                target_warehouse = item.t_warehouse
                target_cost_center = frappe.db.get_value(
                    "Warehouse", target_warehouse, "custom_cost_center"
                )

            debit_account = company.default_inventory_account
            credit_account = company.custom_default_inventory_fund_account

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")

            for item in self.items:
                # cost_center = item.cost_center
                service_area = item.to_program
                subservice_area = item.to_subservice_area
                product = item.to_product
                project = item.custom_target_project
            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_incoming_value,
                    "cost_center": target_cost_center,
                    "credit": 0,
                    "debit_in_account_currency": self.total_incoming_value,
                    "credit_in_account_currency": 0,
                    "program": service_area,
                    "subservice_area": subservice_area,
                    "product": product,
                    "project": project,

                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "cost_center": target_cost_center,
                    "credit": self.total_incoming_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_incoming_value,
                    "program": service_area,
                    "subservice_area": subservice_area,
                    "product": product,
                    "project": project,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()

            debit_account = company.custom_default_inventory_fund_account
            credit_account = company.default_inventory_account

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")
            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_incoming_value,
                    "cost_center": source_cost_center,
                    "credit": 0,
                    "debit_in_account_currency": self.total_incoming_value,
                    "credit_in_account_currency": 0,
                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "cost_center": source_cost_center,
                    "credit": self.total_incoming_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_incoming_value,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()
        
        elif self.stock_entry_type == "Donated Inventory Disposal - Restricted":
            pass

        elif self.purpose == "Material Transfer" and self.add_to_transit:
            debit_account = company.custom_default_stock_in_transit
            credit_account = company.custom_default_stock_transfered_control

            source_cost_center, target_cost_center = "", ""
            for item in self.items:
                source_warehouse = item.s_warehouse
                source_cost_center = frappe.db.get_value(
                    "Warehouse", source_warehouse, "custom_cost_center"
                )

                target_warehouse = item.t_warehouse
                target_cost_center = frappe.db.get_value(
                    "Warehouse", target_warehouse, "custom_cost_center"
                )

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")
            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_incoming_value,
                    "cost_center": source_cost_center,
                    "credit": 0,
                    "debit_in_account_currency": self.total_incoming_value,
                    "credit_in_account_currency": 0,
                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "cost_center": target_cost_center,
                    "credit": self.total_incoming_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_incoming_value,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()

            debit_account = company.custom_default_inventory_fund_account
            credit_account = company.default_inventory_account

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")
            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_incoming_value,
                    "cost_center": source_cost_center,
                    "credit": 0,
                    "debit_in_account_currency": self.total_incoming_value,
                    "credit_in_account_currency": 0,
                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "cost_center": target_cost_center,
                    "credit": self.total_incoming_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_incoming_value,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()
            

        elif self.purpose == "Material Transfer" and self.outgoing_stock_entry:
            debit_account = company.default_inventory_account
            credit_account = company.custom_default_inventory_fund_account

            source_cost_center, target_cost_center = "", ""
            for item in self.items:
                source_warehouse = item.s_warehouse
                source_cost_center = frappe.db.get_value(
                    "Warehouse", source_warehouse, "custom_cost_center"
                )

                target_warehouse = item.t_warehouse
                target_cost_center = frappe.db.get_value(
                    "Warehouse", target_warehouse, "custom_cost_center"
                )

            if not debit_account or not credit_account:
                frappe.throw("Required accounts not found in the company")
            # Create the GL entry for the debit account and update
            debit_entry = self.get_gl_entry_dict()
            debit_entry.update(
                {
                    "account": debit_account,
                    "debit": self.total_incoming_value,
                    "cost_center": source_cost_center,
                    "credit": 0,
                    "debit_in_account_currency": self.total_incoming_value,
                    "credit_in_account_currency": 0,
                }
            )
            debit_gl = frappe.get_doc(debit_entry)
            debit_gl.flags.ignore_permissions = True
            debit_gl.insert()
            debit_gl.submit()

            credit_entry = self.get_gl_entry_dict()
            credit_entry.update(
                {
                    "account": credit_account,
                    "debit": 0,
                    "cost_center": target_cost_center,
                    "credit": self.total_incoming_value,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": self.total_incoming_value,
                }
            )
            credit_gl = frappe.get_doc(credit_entry)
            credit_gl.flags.ignore_permissions = True
            credit_gl.insert()
            credit_gl.submit()

    def get_gl_entry_dict(self):
        cost_center = ""
        service_area = ""
        subservice_area = ""
        product = ""
        project = ""

        for item in self.items:
            cost_center = item.cost_center
            service_area = item.program
            subservice_area = item.subservice_area
            product = item.product
            project = item.project

        return frappe._dict(
            {
                "doctype": "GL Entry",
                "posting_date": self.posting_date,
                # "transaction_date": self.posting_date,
                "party_type": "Donor",
                "party": self.donor,
                "against": f"Stock Entry: {self.name}",
                "against_voucher_type": "Stock Entry",
                "against_voucher": self.name,
                "voucher_type": "Stock Entry",
                "voucher_subtype": self.stock_entry_type,
                "voucher_no": self.name,
                "company": self.company,
                "cost_center": cost_center,
                "program": service_area,
                "subservice_area": subservice_area,
                "product": product,
                "project": project,
            }
        )
    
    def set_total_quantity_count(self):
            self.custom_total_quantity_count = sum([item.qty for item in self.get("items")])

    def set_warehouse_cost_centers(self):
        for item in self.items:
            source_cost_center, target_cost_center = "", ""
            self.project = item.project
            if self.purpose == "Material Receipt":
                target_warehouse = item.t_warehouse
                target_cost_center = frappe.db.get_value(
                    "Warehouse", target_warehouse, "custom_cost_center"
                )
                item.cost_center = target_cost_center
            elif self.purpose == "Material Issue" or self.purpose == "Material Transfer":
                source_warehouse = item.s_warehouse
                source_cost_center = frappe.db.get_value(
                    "Warehouse", source_warehouse, "custom_cost_center"
                )
                item.cost_center = source_cost_center

    # # Check for over quantity
    # def over_quantity_validation():
    #     if target_doc.qty > (source_doc.qty - source_doc.transferred_qty):
    #         frappe.throw("Errorrrrr")

@frappe.whitelist()
def make_stock_in_lost_entry(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.stock_entry_type = "Lost / Wastage"
		target.set_missing_values()
		target.make_serial_and_batch_bundle_for_transfer()

	def update_item(source_doc, target_doc, source_parent):
		target_doc.t_warehouse = ""

		if source_doc.material_request_item and source_doc.material_request:
			add_to_transit = frappe.db.get_value("Stock Entry", source_name, "add_to_transit")
			if add_to_transit:
				warehouse = frappe.get_value(
					"Material Request Item", source_doc.material_request_item, "warehouse"
				)
				target_doc.t_warehouse = warehouse

		target_doc.s_warehouse = source_doc.t_warehouse
		target_doc.qty = source_doc.qty - source_doc.transferred_qty
        
        
            

	doclist = get_mapped_doc(
		"Stock Entry",
		source_name,
		{
			"Stock Entry": {
				"doctype": "Stock Entry",
				"field_map": {"name": "outgoing_stock_entry"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Stock Entry Detail": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"name": "ste_detail",
					"parent": "against_stock_entry",
					"serial_no": "serial_no",
					"batch_no": "batch_no",
				},
				"postprocess": update_item,
				"condition": lambda doc: flt(doc.qty) - flt(doc.transferred_qty) > 0.01,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist