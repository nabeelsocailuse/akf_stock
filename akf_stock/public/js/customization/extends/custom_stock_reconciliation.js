frappe.ui.form.on("Stock Reconciliation Item", {
    custom_new: function(frm, cdt, cdn){
        let row = locals[cdt][cdn];
        if(row.custom_new){
            row.custom_used = 0;
        }
        frm.refresh_field("items")
    },
    custom_used: function(frm, cdt, cdn){
        let row = locals[cdt][cdn];
        if(row.custom_used){
            row.custom_new = 0;
        }
        frm.refresh_field("items")
    }
});