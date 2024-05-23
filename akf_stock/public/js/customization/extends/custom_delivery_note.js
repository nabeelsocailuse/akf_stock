
frappe.ui.form.on("Delivery Note", {
    refresh: function(frm){
        frm.events.custom_set_df_property(frm);
        frm.events.add_custom_buttons(frm);
    },
    custom_set_df_property: function(frm){
        if(!frm.doc.custom_add_to_transit){
            frm.set_df_property("customer", "reqd", 1);
        }else{
            frm.set_df_property("customer", "read_only", 1);
        }
    },
    add_custom_buttons: function(frm){
        if(frm.doc.docstatus==1 && frm.doc.per_installed<100){
            frm.add_custom_button(__('Lost / Wastage'), function() {
                frm.events.make_stock_entry(frm, "Lost / Wastage");
            });
            frm.add_custom_button(__('End Transit'), function() {
                frm.events.make_stock_entry(frm, "Material Transfer");
            });
        }
    },
    make_stock_entry: function(frm, stock_entry_type){
        frappe.call({
            method: "akf_stock.customization.api.delivery_note_to_stock_entry.make_stock_entry",
            args:{
                source_name:  frm.doc.name,
                stock_entry_type:  stock_entry_type
            },
            callback: function(r) {
                if (r.message) {
                    let doc = frappe.model.sync(r.message);
                    frappe.set_route('Form', doc[0].doctype, doc[0].name);
                }
            }
        });
    }
});