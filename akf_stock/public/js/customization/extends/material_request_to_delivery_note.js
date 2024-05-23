frappe.ui.form.on('Material Request', {
    refresh: function (frm) {
        frm.events.delivery_note_in_transit(frm);
        // frm.toggle_reqd('customer', frm.doc.material_request_type=="Customer Provided");
    },
    delivery_note_in_transit: function (frm) {
        if (frm.doc.docstatus == 1 && frm.doc.status != 'Stopped') {
            if (flt(frm.doc.per_ordered, precision) < 100) {
                if (frm.doc.material_request_type === "Material Transfer") {
                    frm.add_custom_button(__("Delivery Note (In Transit)"),
                        () => frm.events.make_delivery_note(frm), __('Create'));
                }
            }
        }
    },
    make_delivery_note: function (frm) {

        frappe.prompt(
            [
                {
                    label: __('In Transit Warehouse'),
                    fieldname: 'in_transit_warehouse',
                    fieldtype: 'Link',
                    options: 'Warehouse',
                    reqd: 1,
                    get_query: () => {
                        return {
                            filters: {
                                'company': frm.doc.company,
                                'is_group': 0,
                                'warehouse_type': 'Transit'
                            }
                        }
                    }
                }
            ],
            (values) => {
                frappe.call({
                    method: "akf_stock.customization.api.material_request_to_delivery_note.make_in_transit_delivery_note",
                    args: {
                        source_name: frm.doc.name,
                        in_transit_warehouse: values.in_transit_warehouse
                    },
                    callback: function (r) {
                        if (r.message) {
                            let doc = frappe.model.sync(r.message);
                            frappe.set_route('Form', doc[0].doctype, doc[0].name);
                        }
                    }
                })
            },
            __('In Transit Transfer'),
            __("Create Delivery Note")
        )
    }
});