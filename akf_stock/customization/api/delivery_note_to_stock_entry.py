import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

@frappe.whitelist()
def make_stock_entry(source_name, stock_entry_type):
    doc = _make_stock_entry_(source_name, stock_entry_type)
    return doc

def _make_stock_entry_(source_name, stock_entry_type, target_doc=None):
	
    def set_missing_values(source, target):
        target.stock_entry_type = stock_entry_type
        target.set_missing_values()
        target.make_serial_and_batch_bundle_for_transfer()
        
        target.custom_delivery_note = source_name
        target.custom_dn_receiving = 1
        
        if(stock_entry_type == "Material Transfer"):
            target.from_warehouse = source.custom_set_in_transit_warehouse
            target.to_warehouse = source.set_target_warehouse
        else:
             target.from_warehouse = source.custom_set_in_transit_warehouse

    def update_item(source_doc, target_doc, source_parent):
        target_doc.t_warehouse = ""

        if source_doc.material_request_item and source_doc.material_request:
            add_to_transit = frappe.db.get_value("Stock Entry", source_name, "add_to_transit")
            if add_to_transit:
                warehouse = frappe.get_value(
                    "Material Request Item", source_doc.material_request_item, "warehouse"
                )
                target_doc.t_warehouse = warehouse
        if(stock_entry_type == "Material Transfer"):
            target_doc.s_warehouse = source_parent.custom_set_in_transit_warehouse
            target_doc.t_warehouse = source_parent.set_target_warehouse
        else:
            target_doc.s_warehouse = source_parent.custom_set_in_transit_warehouse
        # target_doc.qty = source_doc.qty - source_doc.transferred_qty
        target_doc.qty = source_doc.qty

    doclist = get_mapped_doc(
        "Delivery Note",
        source_name,
        {
            "Delivery Note": {
                "doctype": "Stock Entry",
                # "field_map": {"name": "outgoing_stock_entry"},
                # "validation": {"docstatus": ["=", 1]},
            },
            "Delivery Note Item": {
                "doctype": "Stock Entry Detail",
                # "field_map": {
                # 	"name": "ste_detail",
                # 	"parent": "against_stock_entry",
                # 	"serial_no": "serial_no",
                # 	"batch_no": "batch_no",
                # },
                "postprocess": update_item,
                # "condition": lambda doc: flt(doc.qty) - flt(doc.transferred_qty) > 0.01,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist


