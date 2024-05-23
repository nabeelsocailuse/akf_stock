
import json

import frappe
from frappe import _, msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Sum
from frappe.utils import cint, cstr, flt, get_link_to_form, getdate, new_line_sep, nowdate

@frappe.whitelist()
def make_in_transit_delivery_note(source_name, in_transit_warehouse):
	doc = make_delivery_note(source_name, in_transit_warehouse)
	return doc


@frappe.whitelist()
def make_delivery_note(source_name, in_transit_warehouse, target_doc=None):
	def update_item(obj, target, source_parent):
		qty = (
			flt(flt(obj.stock_qty) - flt(obj.ordered_qty)) / target.conversion_factor
			if flt(obj.stock_qty) > flt(obj.ordered_qty)
			else 0
		)
		target.qty = qty
		target.transfer_qty = qty * obj.conversion_factor
		target.conversion_factor = obj.conversion_factor

		if (
			source_parent.material_request_type == "Material Transfer"
			or source_parent.material_request_type == "Customer Provided"
		):
			target.warehouse = obj.from_warehouse

		if source_parent.material_request_type == "Customer Provided":
			target.allow_zero_valuation_rate = 1

		if source_parent.material_request_type == "Material Transfer":
			target.warehouse = obj.from_warehouse

	def set_missing_values(source, target):
		target.purpose = source.material_request_type
		target.set_warehouse = source.set_from_warehouse
		target.set_target_warehouse = source.set_warehouse
		target.custom_set_in_transit_warehouse = in_transit_warehouse

		target.custom_add_to_transit = 1
		target.custom_reference_doctype = "Material Request"
		target.custom_reference_name = source.name

		if source.job_card:
			target.purpose = "Material Transfer for Manufacture"

		if source.material_request_type == "Customer Provided":
			target.purpose = "Material Receipt"

		# target.set_transfer_qty()
		# target.set_actual_qty()
		# target.calculate_rate_and_amount(raise_error_if_no_rate=False)
		target.stock_entry_type = target.purpose
		# target.set_job_card_data()

		if source.job_card:
			job_card_details = frappe.get_all(
				"Job Card", filters={"name": source.job_card}, fields=["bom_no", "for_quantity"]
			)

			if job_card_details and job_card_details[0]:
				target.bom_no = job_card_details[0].bom_no
				target.fg_completed_qty = job_card_details[0].for_quantity
				target.from_bom = 1

	doclist = get_mapped_doc(
		"Material Request",
		source_name,
		{
			"Material Request": {
				"doctype": "Delivery Note",
				# "validation": {
				# 	"docstatus": ["=", 1],
				# 	"material_request_type": ["in", ["Material Transfer", "Material Issue", "Customer Provided"]],
				# },
			},
			"Material Request Item": {
				"doctype": "Delivery Note Item",
				# "field_map": {
				# 	"name": "material_request_item",
				# 	"parent": "material_request",
				# 	"uom": "stock_uom",
				# 	"job_card_item": "job_card_item",
				# },
				"postprocess": update_item,
				# "condition": lambda doc: (
				# 	flt(doc.ordered_qty, doc.precision("ordered_qty"))
				# 	< flt(doc.stock_qty, doc.precision("ordered_qty"))
				# ),
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist

